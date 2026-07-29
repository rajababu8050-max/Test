import os
import json
import re
import time
import asyncio
import requests
from typing import List
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import firebase_admin
from firebase_admin import credentials, firestore

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Firebase Setup via Render Secret Environment Variable
firebase_json_env = os.environ.get("FIREBASE_CREDENTIALS")

if firebase_json_env:
    try:
        cred_dict = json.loads(firebase_json_env)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Firestore Connected Successfully!")
    except Exception as e:
        db = None
        print("❌ Firebase Connection Error:", e)
else:
    db = None
    print("❌ FIREBASE_CREDENTIALS Environment Variable missing!")

# API Keys from Render Environment Variables
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Semaphore: Max 2 parallel executions to prevent network/upload timeouts
semaphore = asyncio.Semaphore(2)

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Call Quality Auditor Pro - Pharma Upsell Edition</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen p-4 md:p-8 font-sans">
    <div class="max-w-6xl mx-auto space-y-6">
        
        <div class="text-center space-y-2">
            <h1 class="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">
                AI Call Quality Auditor Pro
            </h1>
            <p class="text-slate-400 text-sm">Pharma Upsell Metrics Evaluation & Batch Quality Auditing</p>
        </div>

        <!-- Upload Card -->
        <div class="bg-slate-800 border-2 border-dashed border-slate-600 rounded-2xl p-6 text-center">
            <div class="space-y-3">
                <div class="w-12 h-12 bg-blue-500/10 text-blue-400 rounded-full flex items-center justify-center mx-auto text-xl font-bold">🎙️</div>
                <p id="fileName" class="text-sm font-medium text-slate-200">Select Audio File(s) (.mp3, .wav)</p>
                <input type="file" id="audioInput" accept="audio/*" multiple class="hidden" onchange="fileSelected(event)">
                
                <div class="flex justify-center gap-3">
                    <button type="button" onclick="document.getElementById('audioInput').click()" class="bg-slate-700 hover:bg-slate-600 text-white font-medium px-4 py-2 rounded-xl text-sm">
                        Browse Files
                    </button>
                    <button type="button" onclick="uploadAudioBatch()" class="bg-blue-600 hover:bg-blue-500 text-white font-medium px-5 py-2 rounded-xl text-sm shadow-lg shadow-blue-500/20">
                        Start Batch Analysis
                    </button>
                </div>
            </div>
            <div id="loader" class="hidden mt-4 text-xs text-blue-400 animate-pulse font-medium">
                ⏳ Auditing speech, analyzing Pharma Upsell metrics & generating summary... Please wait...
            </div>
        </div>

        <!-- Multi-Results Container -->
        <div id="batchResultsContainer" class="hidden space-y-4">
            <div class="flex justify-between items-center text-slate-300 font-semibold border-b border-slate-800 pb-2 flex-wrap gap-2">
                <span>Batch Processing Results</span>
                <div class="flex gap-2">
                    <button type="button" onclick="downloadExcel()" class="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-4 py-2 rounded-xl flex items-center gap-1 shadow-lg shadow-emerald-600/20">
                        📊 Export Detailed Excel (.xlsx)
                    </button>
                    <button type="button" onclick="downloadPDF()" class="bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold px-4 py-2 rounded-xl flex items-center gap-1">
                        📥 Export PDF Report
                    </button>
                </div>
            </div>
            <div id="resultsList" class="space-y-4"></div>
        </div>

        <!-- History Table Section -->
        <div class="bg-slate-800 border border-slate-700 rounded-2xl p-6 space-y-4 shadow-lg">
            <div class="flex justify-between items-center border-b border-slate-700 pb-3">
                <h3 class="text-sm font-semibold text-slate-300">🔥 Firebase Cloud Audits History</h3>
                <div class="flex gap-2">
                    <button type="button" onclick="exportHistoryExcel()" class="text-xs bg-emerald-700 hover:bg-emerald-600 px-3 py-1.5 rounded-lg text-white font-medium flex items-center gap-1">
                        📊 Export History to Excel
                    </button>
                    <button type="button" onclick="loadHistory()" class="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded-lg text-slate-300">Refresh</button>
                </div>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs text-slate-400">
                    <thead class="bg-slate-700/50 text-slate-300 uppercase font-semibold">
                        <tr>
                            <th class="p-2">File</th>
                            <th class="p-2">Score</th>
                            <th class="p-2">Upsell Opp.</th>
                            <th class="p-2">Pitch Done</th>
                            <th class="p-2">Successful</th>
                            <th class="p-2">PL Pitched</th>
                            <th class="p-2">Date</th>
                        </tr>
                    </thead>
                    <tbody id="historyTable">
                        <tr><td colspan="7" class="p-3 text-center text-slate-500">Loading history...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

    </div>

    <script>
        var selectedFiles = [];
        var currentBatchResults = [];
        var historyDataList = [];

        function fileSelected(e) {
            selectedFiles = Array.from(e.target.files);
            if(selectedFiles.length > 0) {
                document.getElementById('fileName').innerText = selectedFiles.length + " file(s) selected";
            }
        }

        async function uploadAudioBatch() {
            if(selectedFiles.length === 0) {
                alert("Pehle audio file(s) select karein!");
                return;
            }

            document.getElementById('loader').classList.remove('hidden');
            document.getElementById('batchResultsContainer').classList.add('hidden');
            
            var formData = new FormData();
            selectedFiles.forEach(function(file) {
                formData.append("files", file);
            });

            try {
                var res = await fetch("/api/analyze-batch", { method: "POST", body: formData });
                var batchData = await res.json();
                if(!res.ok) throw new Error(batchData.detail || "Server error");

                currentBatchResults = batchData.results || [];
                renderBatchResults(currentBatchResults);
                document.getElementById('batchResultsContainer').classList.remove('hidden');
                loadHistory();
            } catch(err) {
                alert("Error: " + err.message);
            } finally {
                document.getElementById('loader').classList.add('hidden');
            }
        }

        function renderBatchResults(results) {
            var container = document.getElementById('resultsList');
            container.innerHTML = "";

            results.forEach(function(item) {
                if(item.status !== "success") {
                    container.innerHTML += '<div class="bg-red-900/30 border border-red-700 p-4 rounded-xl text-red-300 text-xs">❌ Failed to analyze <b>' + item.filename + '</b>: ' + (item.error || 'Error') + '</div>';
                    return;
                }

                var data = item.data || {};
                var evalData = data.evaluation || {};
                var pharma = evalData.pharma_upsell_metrics || {};
                var metrics = data.metrics || {};
                var transcript = data.transcript || [];
                
                var card = document.createElement('div');
                card.className = "bg-slate-800 border border-slate-700 rounded-2xl p-5 shadow-lg space-y-4";
                
                var transcriptHtml = "";
                transcript.forEach(function(t) {
                    var colorClass = t.speaker === 'Agent' ? 'text-blue-400' : 'text-emerald-400';
                    transcriptHtml += '<div class="mb-1"><b class="' + colorClass + '">' + t.speaker + ':</b> ' + t.text + '</div>';
                });

                var strengthsHtml = "";
                (evalData.strengths || []).forEach(function(s) {
                    strengthsHtml += '<li>' + s + '</li>';
                });

                var improvementsHtml = "";
                (evalData.improvements || []).forEach(function(i) {
                    improvementsHtml += '<li>' + i + '</li>';
                });

                var fmtBool = function(val) {
                    return val ? '<span class="text-emerald-400 font-bold">YES</span>' : '<span class="text-rose-400 font-bold">NO</span>';
                };

                card.innerHTML = 
                    '<div class="flex justify-between items-center border-b border-slate-700 pb-3">' +
                        '<h3 class="font-bold text-blue-400 text-sm">📁 ' + item.filename + '</h3>' +
                        '<span class="text-emerald-400 font-extrabold text-lg">' + (evalData.overall_score || 0) + '/100</span>' +
                    '</div>' +
                    
                    '<!-- Call Audio Metrics -->' +
                    '<div class="grid grid-cols-3 gap-2 text-center text-xs">' +
                        '<div class="bg-slate-900/50 p-2 rounded-lg">' +
                            '<span class="text-slate-500 block text-[10px]">PACE</span>' +
                            '<span class="font-bold text-blue-400">' + (metrics.wpm || 0) + ' WPM</span>' +
                        '</div>' +
                        '<div class="bg-slate-900/50 p-2 rounded-lg">' +
                            '<span class="text-slate-500 block text-[10px]">DURATION</span>' +
                            '<span class="font-bold text-indigo-400">' + Math.round(metrics.duration || 0) + 's</span>' +
                        '</div>' +
                        '<div class="bg-slate-900/50 p-2 rounded-lg">' +
                            '<span class="text-slate-500 block text-[10px]">WORDS</span>' +
                            '<span class="font-bold text-amber-400">' + (metrics.total_words || 0) + '</span>' +
                        '</div>' +
                    '</div>' +

                    '<!-- Pharma Upsell Audit Grid -->' +
                    '<div class="bg-slate-900/70 p-3 rounded-xl border border-slate-700/60 space-y-2">' +
                        '<div class="font-bold text-emerald-400 text-[11px] uppercase tracking-wide border-b border-slate-800 pb-1">💊 Pharma Upsell Metrics</div>' +
                        '<div class="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">' +
                            '<div class="bg-slate-800/80 p-2 rounded border border-slate-700/40">Upsell Opp. Available: ' + fmtBool(pharma.upsell_opportunity_available) + '</div>' +
                            '<div class="bg-slate-800/80 p-2 rounded border border-slate-700/40">Upsell Pitch Done: ' + fmtBool(pharma.upsell_pitch_done) + '</div>' +
                            '<div class="bg-slate-800/80 p-2 rounded border border-slate-700/40">Pitch Ineffective: ' + fmtBool(pharma.upsell_pitch_ineffective) + '</div>' +
                            '<div class="bg-slate-800/80 p-2 rounded border border-slate-700/40">Successful Upsell: ' + fmtBool(pharma.successful_upsell) + '</div>' +
                            '<div class="bg-slate-800/80 p-2 rounded border border-slate-700/40">Quantity Increase Attempt: ' + fmtBool(pharma.quantity_increase_attempt) + '</div>' +
                            '<div class="bg-slate-800/80 p-2 rounded border border-slate-700/40">PL Product Pitched: ' + fmtBool(pharma.pl_product_pitched) + '</div>' +
                        '</div>' +
                    '</div>' +

                    '<div class="text-xs text-slate-300 bg-slate-900/60 p-3 rounded-xl border border-slate-700/50 space-y-1">' +
                        '<div class="font-bold text-blue-300 text-[11px] uppercase tracking-wide">Detailed Call Summary</div>' +
                        '<p class="text-slate-300 leading-relaxed">' + (evalData.summary || "N/A") + '</p>' +
                    '</div>' +
                    '<div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">' +
                        '<div class="bg-slate-900/40 p-3 rounded-xl border border-slate-700/50">' +
                            '<h5 class="font-bold text-emerald-400 mb-1">✅ Strengths</h5>' +
                            '<ul class="list-disc list-inside text-slate-300 space-y-1">' + strengthsHtml + '</ul>' +
                        '</div>' +
                        '<div class="bg-slate-900/40 p-3 rounded-xl border border-slate-700/50">' +
                            '<h5 class="font-bold text-amber-400 mb-1">⚠️ Improvements</h5>' +
                            '<ul class="list-disc list-inside text-slate-300 space-y-1">' + improvementsHtml + '</ul>' +
                        '</div>' +
                    '</div>' +
                    '<details class="bg-slate-900/40 p-3 rounded-xl border border-slate-700/50 text-xs text-slate-300">' +
                        '<summary class="font-bold text-slate-400 cursor-pointer">📄 Click to view Full Diarized Transcript</summary>' +
                        '<div class="mt-3 space-y-2 max-h-48 overflow-y-auto pr-2 pt-2 border-t border-slate-800">' + transcriptHtml + '</div>' +
                    '</details>';
                
                container.appendChild(card);
            });
        }

        async function loadHistory() {
            try {
                var res = await fetch("/api/history");
                var list = await res.json();
                historyDataList = list || [];
                var hTable = document.getElementById('historyTable');
                if(!list || list.length === 0) {
                    hTable.innerHTML = '<tr><td colspan="7" class="p-3 text-center text-slate-500">No past audits in Firebase.</td></tr>';
                    return;
                }
                hTable.innerHTML = "";
                list.forEach(function(item) {
                    var p = item.pharma_metrics || {};
                    hTable.innerHTML += 
                        '<tr class="border-b border-slate-700/50">' +
                            '<td class="p-2 font-medium text-slate-200">' + item.filename + '</td>' +
                            '<td class="p-2 text-emerald-400 font-bold">' + item.score + '/100</td>' +
                            '<td class="p-2">' + (p.upsell_opportunity_available ? '✅' : '❌') + '</td>' +
                            '<td class="p-2">' + (p.upsell_pitch_done ? '✅' : '❌') + '</td>' +
                            '<td class="p-2">' + (p.successful_upsell ? '✅' : '❌') + '</td>' +
                            '<td class="p-2">' + (p.pl_product_pitched ? '✅' : '❌') + '</td>' +
                            '<td class="p-2 text-slate-500">' + item.created_at + '</td>' +
                        '</tr>';
                });
            } catch(e) {
                console.error("History load error:", e);
            }
        }

        function downloadExcel() {
            if(!currentBatchResults || currentBatchResults.length === 0) {
                alert("Koi analysis data nahi hai export karne ke liye!");
                return;
            }

            var summaryRows = [];
            var transcriptRows = [];

            currentBatchResults.forEach(function(item) {
                if(item.status === "success") {
                    var data = item.data || {};
                    var evalData = data.evaluation || {};
                    var pharma = evalData.pharma_upsell_metrics || {};
                    var metrics = data.metrics || {};
                    var transcript = data.transcript || [];

                    summaryRows.push({
                        "File Name": item.filename,
                        "QA Score (/100)": evalData.overall_score || 0,
                        "Pace (WPM)": metrics.wpm || 0,
                        "Call Duration (Sec)": Math.round(metrics.duration || 0),
                        "Upsell Opportunity Available": pharma.upsell_opportunity_available ? "Yes" : "No",
                        "Upsell Pitch Done": pharma.upsell_pitch_done ? "Yes" : "No",
                        "Upsell Pitch Ineffective": pharma.upsell_pitch_ineffective ? "Yes" : "No",
                        "Successful Upsell": pharma.successful_upsell ? "Yes" : "No",
                        "Quantity Increase Attempt": pharma.quantity_increase_attempt ? "Yes" : "No",
                        "PL Product Pitched": pharma.pl_product_pitched ? "Yes" : "No",
                        "Complete Call Summary": evalData.summary || "",
                        "Key Strengths": (evalData.strengths || []).map(function(s, idx) { return (idx+1) + ". " + s; }).join("\\n"),
                        "Areas of Improvement": (evalData.improvements || []).map(function(i, idx) { return (idx+1) + ". " + i; }).join("\\n")
                    });

                    transcript.forEach(function(t) {
                        transcriptRows.push({
                            "File Name": item.filename,
                            "Speaker": t.speaker,
                            "Dialogue / Statement": t.text
                        });
                    });
                }
            });

            var workbook = XLSX.utils.book_new();

            var summarySheet = XLSX.utils.json_to_sheet(summaryRows);
            summarySheet['!cols'] = [
                { wch: 25 }, { wch: 15 }, { wch: 12 }, { wch: 18 },
                { wch: 22 }, { wch: 18 }, { wch: 20 }, { wch: 18 },
                { wch: 22 }, { wch: 18 }, { wch: 50 }, { wch: 35 }, { wch: 35 }
            ];
            XLSX.utils.book_append_sheet(workbook, summarySheet, "Pharma Call Audit Summary");

            if(transcriptRows.length > 0) {
                var transcriptSheet = XLSX.utils.json_to_sheet(transcriptRows);
                transcriptSheet['!cols'] = [
                    { wch: 25 }, { wch: 15 }, { wch: 85 }
                ];
                XLSX.utils.book_append_sheet(workbook, transcriptSheet, "Full Call Transcripts");
            }

            var dateStr = new Date().toISOString().slice(0, 10);
            XLSX.writeFile(workbook, "Pharma_Call_Audit_Analysis_" + dateStr + ".xlsx");
        }

        function exportHistoryExcel() {
            if(!historyDataList || historyDataList.length === 0) {
                alert("History empty hai!");
                return;
            }

            var exportRows = historyDataList.map(function(item) {
                var p = item.pharma_metrics || {};
                return {
                    "File Name": item.filename,
                    "QA Score": item.score,
                    "Pace (WPM)": item.wpm,
                    "Upsell Opp.": p.upsell_opportunity_available ? "Yes" : "No",
                    "Upsell Pitched": p.upsell_pitch_done ? "Yes" : "No",
                    "Successful Upsell": p.successful_upsell ? "Yes" : "No",
                    "PL Pitched": p.pl_product_pitched ? "Yes" : "No",
                    "Detailed Call Summary": item.summary || "",
                    "Audit Date & Time": item.created_at
                };
            });

            var worksheet = XLSX.utils.json_to_sheet(exportRows);
            worksheet['!cols'] = [
                { wch: 25 }, { wch: 12 }, { wch: 12 }, { wch: 12 },
                { wch: 15 }, { wch: 15 }, { wch: 12 }, { wch: 50 }, { wch: 20 }
            ];

            var workbook = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(workbook, worksheet, "Cloud Audit History");

            var dateStr = new Date().toISOString().slice(0, 10);
            XLSX.writeFile(workbook, "Cloud_Audit_History_" + dateStr + ".xlsx");
        }

        function downloadPDF() {
            var element = document.getElementById('batchResultsContainer');
            var opt = {
                margin:       0.3,
                filename:     "Batch_Pharma_Call_Audit_Report_" + new Date().toISOString().slice(0,10) + ".pdf",
                image:        { type: 'jpeg', quality: 0.98 },
                html2canvas:  { scale: 2, backgroundColor: '#0f172a' },
                jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
            };
            html2pdf().set(opt).from(element).save();
        }

        window.onload = function() {
            loadHistory();
        };
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return HTML_CONTENT

def transcribe_bytes(audio_bytes):
    url = (
        "https://api.deepgram.com/v1/listen?"
        "model=nova-2&"
        "language=hi&"
        "detect_language=true&"
        "diarize=true&"
        "punctuate=true&"
        "utterances=true"
    )
    headers = {
        "Authorization": "Token " + DEEPGRAM_API_KEY,
        "Content-Type": "audio/mp3"
    }
    response = requests.post(url, headers=headers, data=audio_bytes, timeout=120)
    if response.status_code != 200:
        raise Exception(f"Deepgram Error ({response.status_code}): {response.text}")
        
    data = response.json()
    duration = data.get("metadata", {}).get("duration", 1)
    utterances = data.get("results", {}).get("utterances", [])
    
    formatted_transcript = []
    total_words = 0
    
    for u in utterances:
        speaker_name = "Agent" if u['speaker'] == 0 else "Customer"
        text = u["transcript"].strip()
        total_words += len(text.split())
        
        if formatted_transcript and formatted_transcript[-1]["speaker"] == speaker_name:
            formatted_transcript[-1]["text"] += " " + text
        else:
            formatted_transcript.append({"speaker": speaker_name, "text": text})
            
    wpm = int((total_words / duration) * 60) if duration > 0 else 0
    
    metrics = {
        "duration": duration,
        "total_words": total_words,
        "wpm": wpm
    }
    
    return formatted_transcript, metrics

def evaluate_quality(transcript):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
    Aap ek Senior Pharma Call Center Quality Assurance (QA) Manager hain.
    Niche diya gaya call transcript poori tarah analyze karke AGENT ka Quality Score (0-100), Pharma Upsell Metrics aur comprehensive audit report tayyar karein.
    
    Transcript:
    {json.dumps(transcript, indent=2)}
    
    Pharma Upsell Metrics Evaluation Criteria (Set boolean true/false for each):
    1. upsell_opportunity_available: Kya customer ke order/inquiry me complementary medicine, health supplement, extra quantity, ya substitute product cross-sell/upsell karne ka mauka tha?
    2. upsell_pitch_done: Kya agent ne kisi bhi tarah ka upsell product/offer pitch karne ki koshish ki?
    3. upsell_pitch_ineffective: Kya agent ki pitch kamzor/ineffective thi jisse customer ne mana kar diya ya agent clear explanation nahi de paya?
    4. successful_upsell: Kya customer ne upsell offer accept karke additional product kharida?
    5. quantity_increase_attempt: Kya agent ne ordered product ki quantity/pack size badhane ki koshish ki (e.g., 1 strip ki jagah 3 strips ya monthly pack)?
    6. pl_product_pitched: Kya agent ne Private Label (PL) / Store Brand / Substitute product suggest/pitch kiya?

    Requirements:
    - 'summary' field me call ka COMPREHENSIVE aur DETAILED SUMMARY (in-depth 4-6 lines) Hindi/Hinglish me likhein.
    - 'strengths' field me Agent ke strong points add karein.
    - 'improvements' field me areas of improvement detail me add karein.
    
    Output STRICTLY valid JSON format me dein without markdown code block tags:
    {{
        "overall_score": 85,
        "summary": "Detailed call summary covering customer query, agent response, upsell attempt, and overall conversation flow...",
        "pharma_upsell_metrics": {{
            "upsell_opportunity_available": true,
            "upsell_pitch_done": true,
            "upsell_pitch_ineffective": false,
            "successful_upsell": false,
            "quantity_increase_attempt": true,
            "pl_product_pitched": false
        }},
        "strengths": ["Point 1", "Point 2"],
        "improvements": ["Point 1", "Point 2"]
    }}
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise Exception(f"Gemini Error ({response.status_code}): {response.text}")
        
    res_data = response.json()
    gemini_raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
    clean_json = re.sub(r'```(?:json)?\n?', '', gemini_raw_text).replace('```', '').strip()
    return json.loads(clean_json)

async def process_single_file(file: UploadFile):
    try:
        audio_bytes = await file.read()
        
        loop = asyncio.get_event_loop()
        transcript, metrics = await loop.run_in_executor(None, transcribe_bytes, audio_bytes)
        evaluation = await loop.run_in_executor(None, evaluate_quality, transcript)
        
        created_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        if db:
            try:
                audit_data = {
                    "filename": file.filename,
                    "score": evaluation.get("overall_score", 0),
                    "summary": evaluation.get("summary", ""),
                    "pharma_metrics": evaluation.get("pharma_upsell_metrics", {}),
                    "wpm": metrics["wpm"],
                    "created_at": created_time,
                    "timestamp": firestore.SERVER_TIMESTAMP
                }
                db.collection("audits").add(audit_data)
            except Exception as fe:
                print("Firebase Write Error:", fe)

        return {
            "status": "success",
            "filename": file.filename,
            "data": {
                "metrics": metrics,
                "transcript": transcript,
                "evaluation": evaluation
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "filename": file.filename,
            "error": str(e)
        }

async def process_single_file_limited(file: UploadFile):
    async with semaphore:
        return await process_single_file(file)

@app.post("/api/analyze-batch")
async def analyze_audio_batch(files: List[UploadFile] = File(...)):
    tasks = [process_single_file_limited(file) for file in files]
    results = await asyncio.gather(*tasks)
    return {"results": results}

@app.get("/api/history")
async def get_history():
    if not db:
        return []
    try:
        try:
            docs = db.collection("audits").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(20).stream()
            history = []
            for doc in docs:
                data = doc.to_dict()
                history.append({
                    "filename": data.get("filename", ""),
                    "score": data.get("score", 0),
                    "summary": data.get("summary", ""),
                    "pharma_metrics": data.get("pharma_metrics", {}),
                    "wpm": data.get("wpm", 0),
                    "created_at": data.get("created_at", "")
                })
            return history
        except Exception as e1:
            print("Ordered Query Failed, trying fallback stream:", e1)
            docs = db.collection("audits").limit(20).stream()
            history = []
            for doc in docs:
                data = doc.to_dict()
                history.append({
                    "filename": data.get("filename", ""),
                    "score": data.get("score", 0),
                    "summary": data.get("summary", ""),
                    "pharma_metrics": data.get("pharma_metrics", {}),
                    "wpm": data.get("wpm", 0),
                    "created_at": data.get("created_at", "")
                })
            return history
    except Exception as e:
        print("Firebase Get History Error:", e)
        return []

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
