import os
import json
import re
import asyncio
import requests
from typing import List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Body
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

# Firebase Setup
firebase_json_env = os.environ.get("FIREBASE_CREDENTIALS")

db = None
if firebase_json_env:
    try:
        cred_dict = json.loads(firebase_json_env)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Firestore Connected Successfully!")
    except Exception as e:
        print("❌ Firebase Connection Error:", e)
else:
    print("⚠️ FIREBASE_CREDENTIALS Environment Variable missing! Running with default in-memory storage.")

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

semaphore = asyncio.Semaphore(2)

# Default Standard Metrics
DEFAULT_METRICS = [
    {"key": "upsell_opportunity_available", "label": "Upsell Opportunity Available", "description": "Was there a chance to offer an additional product?"},
    {"key": "upsell_pitch_done", "label": "Upsell Pitch Done", "description": "Did the agent pitch an upsell item?"},
    {"key": "upsell_pitch_ineffective", "label": "Pitch Ineffective", "description": "Was the pitch unclear or poorly timed?"},
    {"key": "successful_upsell", "label": "Successful Upsell", "description": "Did the customer accept the upsell?"},
    {"key": "quantity_increase_attempt", "label": "Quantity Increase Attempt", "description": "Did the agent attempt to increase item quantity?"},
    {"key": "pl_product_pitched", "label": "PL Product Pitched", "description": "Did the agent pitch a Private Label product?"}
]

# In-memory fallback if Firebase DB is not configured
IN_MEMORY_METRICS = list(DEFAULT_METRICS)

def get_stored_metrics() -> List[Dict[str, Any]]:
    if not db:
        return IN_MEMORY_METRICS
    try:
        docs = list(db.collection("custom_metrics").stream())
        if not docs:
            # Seed default metrics to Firestore if empty
            for m in DEFAULT_METRICS:
                db.collection("custom_metrics").document(m["key"]).set(m)
            return DEFAULT_METRICS
        metrics = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            metrics.append(data)
        return metrics
    except Exception as e:
        print("❌ Error fetching dynamic metrics from Firebase:", e)
        return IN_MEMORY_METRICS

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Call Quality Auditor Pro</title>
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
            <p class="text-slate-400 text-sm">Pharma Upsell Metrics Evaluation & Dynamic Quality Auditing</p>
        </div>

        <!-- Dynamic Metrics Management Card -->
        <div class="bg-slate-800 border border-slate-700 rounded-2xl p-6 shadow-lg space-y-4">
            <div class="flex justify-between items-center border-b border-slate-700 pb-3">
                <h3 class="text-base font-bold text-emerald-400">⚙️ Dynamic Evaluation Metrics Configurator</h3>
                <button type="button" onclick="openMetricModal()" class="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-3 py-1.5 rounded-xl shadow-lg">
                    + Add New Metric
                </button>
            </div>
            <div id="metricsList" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                <div class="text-slate-500 text-xs">Loading metrics...</div>
            </div>
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
                ⏳ Auditing speech, analyzing metrics & generating summary... Please wait...
            </div>
        </div>

        <!-- Multi-Results Container -->
        <div id="batchResultsContainer" class="hidden space-y-6">
            <div class="flex justify-between items-center text-slate-300 font-semibold border-b border-slate-800 pb-2 flex-wrap gap-2">
                <span class="text-lg text-emerald-400 font-bold">📊 Batch Analysis Summary Report</span>
                <div class="flex gap-2">
                    <button type="button" onclick="downloadExcel()" class="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-4 py-2 rounded-xl shadow-lg">
                        📊 Export Detailed Excel (.xlsx)
                    </button>
                    <button type="button" onclick="downloadPDF()" class="bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold px-4 py-2 rounded-xl">
                        📥 Export PDF Report
                    </button>
                </div>
            </div>

            <!-- Aggregate Summary Table Box -->
            <div id="summaryTableContainer" class="bg-slate-800 border border-slate-700 rounded-2xl p-5 shadow-xl space-y-4">
                <div class="flex justify-between items-center border-b border-slate-700 pb-3">
                    <div>
                        <h3 class="text-base font-bold text-blue-400">💊 Batch Aggregate Metrics Summary</h3>
                        <p class="text-xs text-slate-400" id="summaryTimeSlot">Batch Analytics</p>
                    </div>
                    <span id="totalCallsBadge" class="bg-blue-500/20 text-blue-300 text-xs font-bold px-3 py-1 rounded-full border border-blue-500/30">Total Calls: 0</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm text-slate-300 border-collapse">
                        <thead>
                            <tr class="bg-slate-900/80 text-slate-200 uppercase text-xs border-b border-slate-700">
                                <th class="p-3">Metric</th>
                                <th class="p-3 text-center">Count</th>
                                <th class="p-3 text-center">%</th>
                            </tr>
                        </thead>
                        <tbody id="summaryTableBody" class="divide-y divide-slate-700/50 text-xs md:text-sm">
                        </tbody>
                    </table>
                </div>
            </div>

            <h3 class="text-md font-bold text-slate-300 pt-2 border-b border-slate-800 pb-2">📁 Individual Call Breakdowns</h3>
            <div id="resultsList" class="space-y-4"></div>
        </div>

        <!-- History Table Section -->
        <div class="bg-slate-800 border border-slate-700 rounded-2xl p-6 space-y-4 shadow-lg">
            <div class="flex justify-between items-center border-b border-slate-700 pb-3">
                <h3 class="text-sm font-semibold text-slate-300">🔥 Firebase Cloud Audits History</h3>
                <div class="flex gap-2">
                    <button type="button" onclick="exportHistoryExcel()" class="text-xs bg-emerald-700 hover:bg-emerald-600 px-3 py-1.5 rounded-lg text-white font-medium">
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
                            <th class="p-2">Summary</th>
                            <th class="p-2">Date</th>
                        </tr>
                    </thead>
                    <tbody id="historyTable">
                        <tr><td colspan="4" class="p-3 text-center text-slate-500">Loading history...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

    </div>

    <!-- Modal for Add/Edit Dynamic Metric -->
    <div id="metricModal" class="fixed inset-0 bg-black/70 hidden flex items-center justify-center p-4 z-50">
        <div class="bg-slate-800 border border-slate-700 rounded-2xl p-6 w-full max-w-md space-y-4">
            <h3 id="modalTitle" class="text-lg font-bold text-slate-200">Add Dynamic Metric</h3>
            <input type="hidden" id="metricId">
            <div>
                <label class="text-xs text-slate-400 block mb-1">Metric Key (e.g. greeting_done)</label>
                <input type="text" id="metricKey" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-200" placeholder="e.g. greeting_done">
            </div>
            <div>
                <label class="text-xs text-slate-400 block mb-1">Display Label</label>
                <input type="text" id="metricLabel" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-200" placeholder="e.g. Greeting Completed">
            </div>
            <div>
                <label class="text-xs text-slate-400 block mb-1">Evaluation Rule Description</label>
                <textarea id="metricDesc" rows="3" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-200" placeholder="Describe rule when this is TRUE or FALSE..."></textarea>
            </div>
            <div class="flex justify-end gap-2 pt-2">
                <button type="button" onclick="closeMetricModal()" class="bg-slate-700 hover:bg-slate-600 px-4 py-2 text-xs rounded-xl text-slate-300">Cancel</button>
                <button type="button" onclick="saveMetric()" class="bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-xs rounded-xl text-white font-bold">Save Metric</button>
            </div>
        </div>
    </div>

    <script>
        var selectedFiles = [];
        var currentBatchResults = [];
        var historyDataList = [];
        var currentMetrics = [];

        async function loadMetrics() {
            try {
                var res = await fetch("/api/metrics");
                if(!res.ok) throw new Error("Failed to fetch metrics");
                currentMetrics = await res.json();
            } catch(e) {
                console.error("Failed to load metrics:", e);
                currentMetrics = [
                    {key: "upsell_opportunity_available", label: "Upsell Opportunity Available", description: "Was there a chance to offer an additional product?"},
                    {key: "upsell_pitch_done", label: "Upsell Pitch Done", description: "Did the agent pitch an upsell item?"},
                    {key: "upsell_pitch_ineffective", label: "Pitch Ineffective", description: "Was the pitch unclear or poorly timed?"},
                    {key: "successful_upsell", label: "Successful Upsell", description: "Did the customer accept the upsell?"},
                    {key: "quantity_increase_attempt", label: "Quantity Increase Attempt", description: "Did the agent attempt to increase item quantity?"},
                    {key: "pl_product_pitched", label: "PL Product Pitched", description: "Did the agent pitch a Private Label product?"}
                ];
            }
            renderMetricsList();
        }

        function renderMetricsList() {
            var container = document.getElementById('metricsList');
            container.innerHTML = "";
            if(!currentMetrics || currentMetrics.length === 0) {
                container.innerHTML = '<div class="text-slate-500 text-xs">No metrics configured.</div>';
                return;
            }
            currentMetrics.forEach(function(m) {
                var card = document.createElement('div');
                card.className = "bg-slate-900/60 border border-slate-700/60 p-3 rounded-xl flex justify-between items-start";
                card.innerHTML = 
                    '<div>' +
                        '<div class="font-bold text-xs text-slate-200">' + (m.label || m.key) + '</div>' +
                        '<div class="text-[10px] text-slate-400 font-mono">' + m.key + '</div>' +
                        '<div class="text-[11px] text-slate-400 mt-1">' + (m.description || '') + '</div>' +
                    '</div>' +
                    '<div class="flex gap-2 ml-2">' +
                        '<button type="button" onclick="editMetric(\'' + (m.id || m.key) + '\')" class="text-blue-400 hover:text-blue-300 text-xs font-bold">Edit</button>' +
                        '<button type="button" onclick="deleteMetric(\'' + (m.id || m.key) + '\')" class="text-rose-400 hover:text-rose-300 text-xs font-bold">Delete</button>' +
                    '</div>';
                container.appendChild(card);
            });
        }

        function openMetricModal(metric) {
            document.getElementById('metricId').value = (metric && metric.id) ? metric.id : ((metric && metric.key) ? metric.key : '');
            document.getElementById('metricKey').value = metric ? metric.key : '';
            document.getElementById('metricLabel').value = metric ? metric.label : '';
            document.getElementById('metricDesc').value = metric ? (metric.description || '') : '';
            document.getElementById('modalTitle').innerText = metric ? 'Edit Metric' : 'Add Dynamic Metric';
            document.getElementById('metricKey').disabled = !!metric;
            document.getElementById('metricModal').classList.remove('hidden');
        }

        function closeMetricModal() {
            document.getElementById('metricModal').classList.add('hidden');
        }

        function editMetric(id) {
            var m = (currentMetrics || []).find(x => (x.id === id || x.key === id));
            if(m) openMetricModal(m);
        }

        async function saveMetric() {
            var id = document.getElementById('metricId').value;
            var key = document.getElementById('metricKey').value.trim();
            var label = document.getElementById('metricLabel').value.trim();
            var description = document.getElementById('metricDesc').value.trim();

            if(!key || !label) {
                alert("Key and Label required!");
                return;
            }

            var method = id ? "PUT" : "POST";
            var url = id ? "/api/metrics/" + encodeURIComponent(id) : "/api/metrics";

            try {
                var res = await fetch(url, {
                    method: method,
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ key, label, description })
                });
                if(!res.ok) throw new Error("Save failed");
                closeMetricModal();
                await loadMetrics();
            } catch(e) {
                alert("Error: " + e.message);
            }
        }

        async function deleteMetric(id) {
            if(!confirm("Delete metric?")) return;
            try {
                var res = await fetch("/api/metrics/" + encodeURIComponent(id), { method: "DELETE" });
                if(!res.ok) throw new Error("Delete failed");
                await loadMetrics();
            } catch(e) {
                alert("Error: " + e.message);
            }
        }

        function fileSelected(e) {
            selectedFiles = Array.from(e.target.files);
            if(selectedFiles.length > 0) {
                document.getElementById('fileName').innerText = selectedFiles.length + " file(s) selected";
            }
        }

        async function uploadAudioBatch() {
            if(selectedFiles.length === 0) {
                alert("Please select audio file(s) first!");
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
                setTimeout(loadHistory, 1000);
            } catch(err) {
                alert("Error: " + err.message);
            } finally {
                document.getElementById('loader').classList.add('hidden');
            }
        }

        function renderBatchResults(results) {
            var container = document.getElementById('resultsList');
            container.innerHTML = "";

            var validResults = results.filter(function(r) { return r.status === "success"; });
            var totalCalls = validResults.length;

            // Calculate Aggregate Counts Dynamically for all metrics
            var metricCounts = {};
            (currentMetrics || []).forEach(function(m) { metricCounts[m.key] = 0; });

            validResults.forEach(function(item) {
                var dynamicEval = item.data?.evaluation?.dynamic_metrics || item.data?.evaluation?.pharma_upsell_metrics || {};
                (currentMetrics || []).forEach(function(m) {
                    if (dynamicEval[m.key]) metricCounts[m.key]++;
                });
            });

            function calcPct(val) {
                if (totalCalls === 0) return "0%";
                return Math.round((val / totalCalls) * 100) + "%";
            }

            document.getElementById('totalCallsBadge').innerText = "Total Calls Reviewed: " + totalCalls;
            document.getElementById('summaryTimeSlot').innerText = "Audit Generated On: " + new Date().toLocaleString();

            var summaryHtml = '<tr class="hover:bg-slate-700/30 transition"><td class="p-2.5 font-medium text-slate-200">Total Calls Reviewed</td><td class="p-2.5 text-center font-bold text-blue-400">' + totalCalls + '</td><td class="p-2.5 text-center font-extrabold text-emerald-400">100%</td></tr>';

            (currentMetrics || []).forEach(function(m) {
                var count = metricCounts[m.key] || 0;
                summaryHtml += '<tr class="hover:bg-slate-700/30 transition"><td class="p-2.5 font-medium text-slate-200">' + (m.label || m.key) + '</td><td class="p-2.5 text-center font-bold text-blue-400">' + count + '</td><td class="p-2.5 text-center font-extrabold text-emerald-400">' + calcPct(count) + '</td></tr>';
            });
            document.getElementById('summaryTableBody').innerHTML = summaryHtml;

            // Render Individual Cards
            results.forEach(function(item) {
                if(item.status !== "success") {
                    container.innerHTML += '<div class="bg-red-900/30 border border-red-700 p-4 rounded-xl text-red-300 text-xs">❌ Failed to analyze <b>' + item.filename + '</b>: ' + (item.error || 'Error') + '</div>';
                    return;
                }

                var data = item.data || {};
                var evalData = data.evaluation || {};
                var dynamicMetrics = evalData.dynamic_metrics || evalData.pharma_upsell_metrics || {};
                var metrics = data.metrics || {};
                var transcript = data.transcript || [];
                
                var card = document.createElement('div');
                card.className = "bg-slate-800 border border-slate-700 rounded-2xl p-5 shadow-lg space-y-4";
                
                var transcriptHtml = "";
                transcript.forEach(function(t) {
                    var colorClass = t.speaker === 'Agent' ? 'text-blue-400' : 'text-emerald-400';
                    transcriptHtml += '<div class="mb-1"><b class="' + colorClass + '">' + t.speaker + ':</b> ' + t.text + '</div>';
                });

                var fmtBool = function(val) {
                    return val ? '<span class="text-emerald-400 font-bold">YES</span>' : '<span class="text-rose-400 font-bold">NO</span>';
                };

                var dynamicMetricsHtml = "";
                (currentMetrics || []).forEach(function(m) {
                    var val = dynamicMetrics[m.key];
                    dynamicMetricsHtml += '<div class="bg-slate-800/80 p-2 rounded border border-slate-700/40">' + (m.label || m.key) + ': ' + fmtBool(val) + '</div>';
                });

                card.innerHTML = 
                    '<div class="flex justify-between items-center border-b border-slate-700 pb-3">' +
                        '<h3 class="font-bold text-blue-400 text-sm">📁 ' + item.filename + '</h3>' +
                        '<span class="text-emerald-400 font-extrabold text-lg">' + (evalData.overall_score || 0) + '/100</span>' +
                    '</div>' +
                    '<div class="grid grid-cols-3 gap-2 text-center text-xs">' +
                        '<div class="bg-slate-900/50 p-2 rounded-lg"><span class="text-slate-500 block text-[10px]">PACE</span><span class="font-bold text-blue-400">' + (metrics.wpm || 0) + ' WPM</span></div>' +
                        '<div class="bg-slate-900/50 p-2 rounded-lg"><span class="text-slate-500 block text-[10px]">DURATION</span><span class="font-bold text-indigo-400">' + Math.round(metrics.duration || 0) + 's</span></div>' +
                        '<div class="bg-slate-900/50 p-2 rounded-lg"><span class="text-slate-500 block text-[10px]">WORDS</span><span class="font-bold text-amber-400">' + (metrics.total_words || 0) + '</span></div>' +
                    '</div>' +
                    '<div class="bg-slate-900/70 p-3 rounded-xl border border-slate-700/60 space-y-2">' +
                        '<div class="font-bold text-emerald-400 text-[11px] uppercase tracking-wide border-b border-slate-800 pb-1">💊 Call Metrics Evaluation</div>' +
                        '<div class="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">' + dynamicMetricsHtml + '</div>' +
                    '</div>' +
                    '<div class="text-xs text-slate-300 bg-slate-900/60 p-3 rounded-xl border border-slate-700/50 space-y-1">' +
                        '<div class="font-bold text-blue-300 text-[11px] uppercase tracking-wide">Detailed Call Summary</div>' +
                        '<p class="text-slate-300 leading-relaxed">' + (evalData.summary || "N/A") + '</p>' +
                    '</div>' +
                    '<details class="bg-slate-900/40 p-3 rounded-xl border border-slate-700/50 text-xs text-slate-300">' +
                        '<summary class="font-bold text-slate-400 cursor-pointer">📄 Click to view Full Diarized Transcript</summary>' +
                        '<div class="mt-3 space-y-2 max-h-48 overflow-y-auto pr-2 pt-2 border-t border-slate-800">' + transcriptHtml + '</div>' +
                    '</details>';
                
                container.appendChild(card);
            });
        }

        async function loadHistory() {
            var hTable = document.getElementById('historyTable');
            hTable.innerHTML = '<tr><td colspan="4" class="p-3 text-center text-slate-500">Loading history...</td></tr>';
            try {
                var res = await fetch("/api/history");
                var list = await res.json();
                historyDataList = list || [];
                
                if(!list || list.length === 0) {
                    hTable.innerHTML = '<tr><td colspan="4" class="p-3 text-center text-slate-500">No past audits found.</td></tr>';
                    return;
                }
                hTable.innerHTML = "";
                list.forEach(function(item) {
                    hTable.innerHTML += 
                        '<tr class="border-b border-slate-700/50">' +
                            '<td class="p-2 font-medium text-slate-200">' + (item.filename || 'N/A') + '</td>' +
                            '<td class="p-2 text-emerald-400 font-bold">' + (item.score || 0) + '/100</td>' +
                            '<td class="p-2 text-slate-300 text-xs truncate max-w-xs">' + (item.summary || 'N/A') + '</td>' +
                            '<td class="p-2 text-slate-500">' + (item.created_at || 'N/A') + '</td>' +
                        '</tr>';
                });
            } catch(e) {
                console.error("History load error:", e);
                hTable.innerHTML = '<tr><td colspan="4" class="p-3 text-center text-rose-500">Failed to load history from server.</td></tr>';
            }
        }

        function downloadExcel() {
            if(!currentBatchResults || currentBatchResults.length === 0) return alert("No data to export!");
            var workbook = XLSX.utils.book_new();
            var summarySheet = XLSX.utils.json_to_sheet(currentBatchResults.map(i => ({
                "File Name": i.filename,
                "QA Score": i.data?.evaluation?.overall_score || 0,
                "Summary": i.data?.evaluation?.summary || ""
            })));
            XLSX.utils.book_append_sheet(workbook, summarySheet, "Batch Summary");
            XLSX.writeFile(workbook, "Call_Audit_Report.xlsx");
        }

        function exportHistoryExcel() {
            if(!historyDataList || historyDataList.length === 0) return alert("History is empty!");
            var workbook = XLSX.utils.book_new();
            var sheet = XLSX.utils.json_to_sheet(historyDataList.map(item => ({
                "File Name": item.filename,
                "QA Score": item.score,
                "WPM": item.wpm,
                "Summary": item.summary,
                "Created At": item.created_at
            })));
            XLSX.utils.book_append_sheet(workbook, sheet, "History");
            XLSX.writeFile(workbook, "Cloud_Audit_History.xlsx");
        }

        function downloadPDF() {
            var element = document.getElementById('batchResultsContainer');
            html2pdf().from(element).save("Batch_Call_Audit_Report.pdf");
        }

        window.onload = function() { 
            loadMetrics();
            loadHistory(); 
        };
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return HTML_CONTENT

# ==================== DYNAMIC METRICS API ENDPOINTS ====================

@app.get("/api/metrics")
async def get_metrics():
    return get_stored_metrics()

@app.post("/api/metrics")
async def create_metric(payload: Dict[str, Any] = Body(...)):
    key = payload.get("key", "").strip()
    label = payload.get("label", "").strip()
    description = payload.get("description", "").strip()

    if not key or not label:
        raise HTTPException(status_code=400, detail="Key and Label required")

    key = re.sub(r'[^a-zA-Z0-9_]', '_', key.lower())

    metric_doc = {
        "key": key,
        "label": label,
        "description": description,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if db:
        db.collection("custom_metrics").document(key).set(metric_doc)
    else:
        # Fallback in memory
        IN_MEMORY_METRICS.append(metric_doc)

    return {"status": "success", "data": metric_doc}

@app.put("/api/metrics/{metric_id}")
async def update_metric(metric_id: str, payload: Dict[str, Any] = Body(...)):
    metric_doc = {
        "label": payload.get("label", "").strip(),
        "description": payload.get("description", "").strip(),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if db:
        doc_ref = db.collection("custom_metrics").document(metric_id)
        if doc_ref.get().exists:
            doc_ref.update(metric_doc)
    else:
        for idx, m in enumerate(IN_MEMORY_METRICS):
            if m.get("id") == metric_id or m.get("key") == metric_id:
                IN_MEMORY_METRICS[idx]["label"] = metric_doc["label"]
                IN_MEMORY_METRICS[idx]["description"] = metric_doc["description"]

    return {"status": "success", "data": metric_doc}

@app.delete("/api/metrics/{metric_id}")
async def delete_metric(metric_id: str):
    if db:
        db.collection("custom_metrics").document(metric_id).delete()
    else:
        global IN_MEMORY_METRICS
        IN_MEMORY_METRICS = [m for m in IN_MEMORY_METRICS if m.get("key") != metric_id and m.get("id") != metric_id]

    return {"status": "success", "deleted_id": metric_id}

# ==================== SPEECH & QUALITY AI ENGINE ====================

def transcribe_bytes(audio_bytes):
    url = "https://api.deepgram.com/v1/listen?model=nova-2&language=hi&detect_language=true&diarize=true&punctuate=true&utterances=true"
    headers = {"Authorization": "Token " + DEEPGRAM_API_KEY, "Content-Type": "audio/mp3"}
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
    return formatted_transcript, {"duration": duration, "total_words": total_words, "wpm": wpm}

def evaluate_quality(transcript, dynamic_metrics):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    metrics_schema_prompt = {}
    metrics_rules_text = ""
    for m in dynamic_metrics:
        m_key = m["key"]
        m_label = m.get("label", m_key)
        m_desc = m.get("description", "")
        metrics_schema_prompt[m_key] = True
        metrics_rules_text += f"- `{m_key}` ({m_label}): {m_desc}\n"

    prompt = f"""
    Analyze the call transcript and evaluate the Agent Quality Score (0-100) along with the following Dynamic Metrics.
    
    DYNAMIC METRICS TO EVALUATE (Return true/false for each):
    {metrics_rules_text}

    Transcript:
    {json.dumps(transcript, indent=2)}

    Return JSON ONLY with this exact structural format:
    {{
        "overall_score": 85,
        "summary": "Detailed call summary...",
        "dynamic_metrics": {json.dumps(metrics_schema_prompt, indent=2)},
        "strengths": ["Strong point"],
        "improvements": ["Improvement point"]
    }}
    """
    response = requests.post(url, headers={"Content-Type": "application/json"}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
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
        
        dynamic_metrics = get_stored_metrics()

        transcript, metrics = await loop.run_in_executor(None, transcribe_bytes, audio_bytes)
        evaluation = await loop.run_in_executor(None, evaluate_quality, transcript, dynamic_metrics)
        
        created_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if db:
            try:
                audit_data = {
                    "filename": file.filename,
                    "score": evaluation.get("overall_score", 0),
                    "summary": evaluation.get("summary", ""),
                    "dynamic_metrics": evaluation.get("dynamic_metrics", {}),
                    "wpm": metrics.get("wpm", 0),
                    "created_at": created_time
                }
                db.collection("audits").add(audit_data)
                print(f"✅ Document added to Firebase for {file.filename}")
            except Exception as fe:
                print("❌ Firebase Write Error:", fe)

        return {"status": "success", "filename": file.filename, "data": {"metrics": metrics, "transcript": transcript, "evaluation": evaluation}}
    except Exception as e:
        return {"status": "error", "filename": file.filename, "error": str(e)}

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
        print("❌ Firebase DB Object is None in /api/history")
        return []
    try:
        docs = db.collection("audits").limit(30).stream()
        history = []
        for doc in docs:
            data = doc.to_dict()
            history.append({
                "filename": data.get("filename", "Unknown"),
                "score": data.get("score", 0),
                "summary": data.get("summary", ""),
                "dynamic_metrics": data.get("dynamic_metrics", {}),
                "wpm": data.get("wpm", 0),
                "created_at": data.get("created_at", "")
            })
        
        history.sort(key=lambda x: x["created_at"], reverse=True)
        return history
    except Exception as e:
        print("❌ Firebase Fetch Error:", str(e))
        return []

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
