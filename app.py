import os
import json
import re
import asyncio
import itertools
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Request, Depends, status
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import firebase_admin
from firebase_admin import credentials, firestore, auth

app = FastAPI(title="AI Call Quality Auditor Pro Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= Environment Keys =================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")

# ================= Firebase Setup =================
firebase_json_env = os.environ.get("FIREBASE_CREDENTIALS")

if firebase_json_env:
    try:
        cred_dict = json.loads(firebase_json_env)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase Firestore & Auth Connected Successfully!")
    except Exception as e:
        db = None
        print("❌ Firebase Connection Error:", e)
else:
    db = None
    print("❌ FIREBASE_CREDENTIALS Environment Variable missing!")

# ================= Gemini Setup =================
raw_gemini_keys = os.environ.get("GEMINI_KEYS", os.environ.get("GEMINI_API_KEY", ""))
GEMINI_KEYS = [k.strip() for k in raw_gemini_keys.split(",") if k.strip()]
key_cycle = itertools.cycle(GEMINI_KEYS) if GEMINI_KEYS else None

def get_next_gemini_key():
    if key_cycle:
        return next(key_cycle)
    return ""

GEMINI_MODEL = "gemini-3.6-flash"
semaphore = asyncio.Semaphore(3)

# ================= Smart Caching Variables =================
cached_history_data: Optional[List[Dict[str, Any]]] = None
cache_history_timestamp: Optional[datetime] = None

cached_metrics_data: Optional[List[Dict[str, Any]]] = None
cache_metrics_timestamp: Optional[datetime] = None

HISTORY_CACHE_TTL_SECONDS = 60  
METRICS_CACHE_TTL_SECONDS = 300 

def invalidate_history_cache():
    global cached_history_data, cache_history_timestamp
    cached_history_data = None
    cache_history_timestamp = None

def invalidate_metrics_cache():
    global cached_metrics_data, cache_metrics_timestamp
    cached_metrics_data = None
    cache_metrics_timestamp = None

DEFAULT_METRICS = [
    {"key": "upsell_opportunity_available", "label": "Upsell Opportunity Available", "description": "Was there an opportunity to pitch an upsell or add-on product?"},
    {"key": "upsell_pitch_done", "label": "Upsell Pitch Done", "description": "Did the agent attempt an upsell pitch during the call?"},
    {"key": "upsell_pitch_ineffective", "label": "Pitch Ineffective", "description": "Was the pitch poorly delivered or irrelevant?"},
    {"key": "successful_upsell", "label": "Successful Upsell", "description": "Did the customer agree to the upsell offer?"},
    {"key": "quantity_increase_attempt", "label": "Quantity Increase Attempt", "description": "Did the agent suggest buying a higher quantity?"},
    {"key": "pl_product_pitched", "label": "PL Product Pitched", "description": "Did the agent pitch a Private Label (PL) product?"}
]

def init_default_metrics():
    if db:
        try:
            docs = list(db.collection("metrics").limit(1).stream())
            if not docs:
                for m in DEFAULT_METRICS:
                    db.collection("metrics").add(m)
                print("✅ Seeded Default Metrics to Firestore")
        except Exception as e:
            print("❌ Failed to seed metrics:", e)

init_default_metrics()

# ================= Authentication Dependency =================

async def verify_firebase_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized access. Token missing."
        )
    token = auth_header.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unauthorized: Invalid or expired token ({str(e)})"
        )

# ================= HTML Content (Professional Light Theme) =================

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en" class="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Call Quality Auditor Pro | Enterprise Light Edition</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        brand: {
                            50: '#f0f9ff',
                            100: '#e0f2fe',
                            500: '#0284c7',
                            600: '#0369a1',
                            900: '#0c4a6e'
                        }
                    }
                }
            }
        }
    </script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
    <script src="https://www.gstatic.com/firebasejs/9.22.1/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/9.22.1/firebase-auth-compat.js"></script>
    <link rel="stylesheet" href="https://rsms.me/inter/inter.css">

    <style>
        body { font-family: 'Inter', sans-serif; background-color: #f8fafc; color: #0f172a; }
        
        .card-bg { 
            background: #ffffff; 
            border: 1px solid #e2e8f0; 
            box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
        }

        .inner-bg { background-color: #f1f5f9; color: #0f172a; }

        .text-sub { color: #64748b; }

        .pro-btn {
            background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%);
            transition: all 0.25s ease;
        }
        .pro-btn:hover {
            box-shadow: 0 4px 14px 0 rgba(2, 132, 199, 0.35);
            transform: translateY(-1px);
        }

        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #f8fafc; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 9999px; }
        ::-webkit-scrollbar-thumb:hover { background: #0284c7; }
    </style>
</head>
<body class="min-h-screen antialiased selection:bg-sky-500 selection:text-white">

    <!-- INITIAL FULLSCREEN APP LOADER -->
    <div id="initialAppLoader" class="fixed inset-0 bg-slate-50 flex flex-col items-center justify-center space-y-4 z-[200]">
        <div class="relative flex items-center justify-center">
            <div class="w-16 h-16 border-4 border-sky-200 border-t-sky-600 rounded-full animate-spin"></div>
            <div class="absolute text-sky-700 font-extrabold text-xs tracking-widest">AI</div>
        </div>
        <p class="text-xs font-semibold text-sky-700 uppercase tracking-widest animate-pulse">Auditor Engine Initializing...</p>
    </div>

    <!-- ADMIN LOGIN MODAL -->
    <div id="authModal" class="hidden fixed inset-0 bg-slate-900/40 backdrop-blur-md flex items-center justify-center p-4 z-[100]">
        <div class="card-bg rounded-3xl w-full max-w-md p-8 space-y-6 relative overflow-hidden shadow-2xl">
            <div class="text-center space-y-2 relative z-10">
                <div class="w-14 h-14 bg-gradient-to-tr from-sky-600 to-blue-700 text-white rounded-2xl flex items-center justify-center mx-auto text-2xl font-black shadow-md">
                    ▲
                </div>
                <h2 class="text-2xl font-black tracking-tight text-slate-900">
                    Admin Portal
                </h2>
                <p class="text-xs text-sub">Sign in with authorized admin credentials</p>
            </div>
            <form onsubmit="handleLogin(event)" class="space-y-4 relative z-10">
                <div>
                    <label class="block text-[10px] font-bold text-sub mb-1.5 uppercase tracking-wider">Admin Email</label>
                    <input type="email" id="adminEmail" required placeholder="admin@enterprise.com" class="w-full card-bg border border-slate-300 rounded-xl px-4 py-2.5 text-xs text-slate-900 focus:outline-none focus:border-sky-600 transition">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-sub mb-1.5 uppercase tracking-wider">Password</label>
                    <input type="password" id="adminPassword" required placeholder="••••••••" class="w-full card-bg border border-slate-300 rounded-xl px-4 py-2.5 text-xs text-slate-900 focus:outline-none focus:border-sky-600 transition">
                </div>
                <div id="authError" class="text-rose-600 text-xs text-center hidden font-medium p-2 bg-rose-50 rounded-lg border border-rose-200"></div>
                <button type="submit" id="loginBtn" class="w-full pro-btn text-white font-bold py-3 rounded-xl text-xs transition shadow-md tracking-wider">
                    AUTHENTICATE
                </button>
            </form>
        </div>
    </div>

    <!-- MAIN PROTECTED DASHBOARD CONTENT -->
    <div id="dashboardContent" class="hidden max-w-7xl mx-auto p-4 md:p-8 space-y-8">
        
        <!-- HEADER NAVBAR -->
        <div class="flex justify-between items-center border-b border-slate-200 pb-6 flex-wrap gap-4">
            <div>
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-gradient-to-tr from-sky-600 to-blue-700 rounded-xl flex items-center justify-center text-lg font-black text-white shadow-md">
                        ▲
                    </div>
                    <div>
                        <h1 onclick="goToHome()" class="text-2xl md:text-3xl font-black tracking-tight cursor-pointer text-slate-900 hover:text-sky-700 transition">
                            Auditor.AI <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-sky-100 border border-sky-200 text-sky-800 align-middle">PRO</span>
                        </h1>
                        <p class="text-xs text-sub font-medium">Enterprise Audio Quality Intelligence & Bulk Auditor</p>
                    </div>
                </div>
            </div>

            <div class="flex items-center gap-3 flex-wrap">
                <a href="/ai.html" class="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white font-bold px-4 py-2.5 rounded-xl text-xs shadow-md flex items-center gap-2 transition transform hover:-translate-y-0.5">
                    ✨ AI Quality Score
                </a>
                <button onclick="openMetricModal()" class="card-bg border border-slate-300 hover:border-sky-500 text-slate-700 font-semibold px-4 py-2.5 rounded-xl text-xs flex items-center gap-2 transition shadow-sm">
                    ⚙️ Manage Metrics
                </button>
                
                <div class="flex items-center gap-2 inner-bg border border-slate-200 px-3 py-1.5 rounded-xl">
                    <span class="text-xs text-sky-800 font-semibold flex items-center gap-1.5">
                        <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        <span id="userDisplayName">Loading...</span>
                    </span>
                    <button onclick="handleLogout()" class="bg-rose-50 hover:bg-rose-100 text-rose-600 font-semibold px-2.5 py-1 rounded-lg text-xs transition border border-rose-200 ml-1">
                        Logout
                    </button>
                </div>
            </div>
        </div>

        <!-- UPLOAD BATCH SECTION -->
        <div class="card-bg rounded-3xl p-8 text-center shadow-lg relative overflow-hidden group border border-slate-200">
            <div class="max-w-xl mx-auto space-y-4 relative z-10">
                <div class="w-16 h-16 bg-sky-50 border border-sky-100 text-sky-600 rounded-2xl flex items-center justify-center mx-auto text-2xl font-bold shadow-inner">
                    🎙️
                </div>
                <div>
                    <h3 class="text-lg font-bold text-slate-900">Upload Call Audio Batches</h3>
                    <p id="fileName" class="text-xs text-sub mt-1">Select MP3, WAV, or M4A audio files for automated intelligence auditing</p>
                </div>
                <input type="file" id="audioInput" accept="audio/*" multiple class="hidden" onchange="fileSelected(event)">
                <div class="flex justify-center gap-3 pt-2">
                    <button type="button" onclick="document.getElementById('audioInput').click()" class="inner-bg border border-slate-300 hover:border-sky-500 font-semibold px-5 py-2.5 rounded-xl text-xs transition text-slate-700">
                        📁 Browse Audio
                    </button>
                    <button type="button" onclick="uploadAudioBatch()" class="pro-btn text-white font-bold px-6 py-2.5 rounded-xl text-xs transition shadow-md tracking-wide">
                        🚀 Start Bulk Analysis
                    </button>
                </div>
            </div>

            <!-- Progress Bar -->
            <div id="progressContainer" class="hidden mt-6 max-w-md mx-auto space-y-2">
                <div class="w-full bg-slate-200 rounded-full h-2 overflow-hidden p-0.5 border border-slate-300">
                    <div id="progressBar" class="bg-gradient-to-r from-sky-500 to-blue-600 h-1.5 rounded-full transition-all duration-300" style="width: 0%"></div>
                </div>
                <div id="loaderText" class="text-xs text-sky-700 font-semibold">⚡ Auditing... 0 / 0 Completed</div>
            </div>
        </div>

        <!-- BATCH RESULTS DISPLAY -->
        <div id="batchResultsContainer" class="hidden space-y-6">
            <div class="flex justify-between items-center font-semibold border-b border-slate-200 pb-3 flex-wrap gap-2">
                <span class="text-base text-sky-800 font-bold flex items-center gap-2">
                    📊 Batch Intelligence Report
                </span>
                <div class="flex gap-2">
                    <button type="button" onclick="downloadExcel()" class="bg-emerald-50 border border-emerald-200 hover:bg-emerald-600 hover:text-white text-emerald-700 text-xs font-bold px-4 py-2 rounded-xl transition flex items-center gap-1.5 shadow-sm">
                        📊 Export Excel (.xlsx)
                    </button>
                    <button type="button" onclick="downloadPDF()" class="inner-bg border border-slate-300 hover:border-slate-400 text-slate-700 text-xs font-bold px-4 py-2 rounded-xl transition">
                        📥 Export PDF
                    </button>
                </div>
            </div>

            <div id="summaryTableContainer" class="card-bg rounded-2xl p-6 shadow-md space-y-4">
                <div class="flex justify-between items-center border-b border-slate-200 pb-4">
                    <div>
                        <h3 class="text-xs font-extrabold text-sky-800 uppercase tracking-widest">Aggregate Batch KPI Summary</h3>
                        <p class="text-xs text-sub" id="summaryTimeSlot">Batch Analytics</p>
                    </div>
                    <span id="totalCallsBadge" class="bg-sky-50 text-sky-700 text-xs font-bold px-3 py-1 rounded-full border border-sky-200">Total Calls: 0</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs border-collapse">
                        <thead>
                            <tr class="inner-bg uppercase text-[10px] font-bold tracking-wider text-slate-600 border-b border-slate-200">
                                <th class="p-3">Metric</th>
                                <th class="p-3 text-center">Positive Count</th>
                                <th class="p-3 text-center">Compliance %</th>
                            </tr>
                        </thead>
                        <tbody id="summaryTableBody" class="divide-y divide-slate-100 text-xs"></tbody>
                    </table>
                </div>
            </div>

            <h3 class="text-xs font-extrabold text-slate-500 uppercase tracking-widest pt-4 border-b border-slate-200 pb-2">📁 Individual Call Audits</h3>
            <div id="resultsList" class="space-y-4"></div>
        </div>

        <!-- FIREBASE CLOUD HISTORY TABLE -->
        <div class="card-bg rounded-2xl p-6 space-y-6 shadow-md border border-slate-200">
            <div class="flex justify-between items-center border-b border-slate-200 pb-4 flex-wrap gap-3">
                <div class="flex items-center gap-3 flex-wrap">
                    <h3 class="text-xs font-extrabold text-slate-800 uppercase tracking-widest">🔥 Cloud Audits History</h3>
                    <span id="totalHistoryBadge" class="bg-sky-50 text-sky-700 text-xs font-bold px-2.5 py-0.5 rounded-full border border-sky-200">0 Records</span>
                    <span id="selectedCountBadge" class="bg-emerald-50 text-emerald-700 text-xs font-bold px-2.5 py-0.5 rounded-full border border-emerald-200 transition">
                        Selected: 0
                    </span>
                </div>
                <div class="flex gap-2 flex-wrap items-center">
                    <button type="button" id="exportAllBtn" onclick="exportHistoryExcel(event)" class="text-xs bg-emerald-50 border border-emerald-200 hover:bg-emerald-600 text-emerald-700 hover:text-white px-3 py-1.5 rounded-lg font-semibold transition shadow-sm">
                        📊 Export ALL Excel
                    </button>
                    <button type="button" onclick="exportSelectedExcel()" class="text-xs inner-bg border border-slate-300 hover:border-slate-400 px-3 py-1.5 rounded-lg text-slate-700 font-semibold transition">
                        📋 Export Marked
                    </button>
                    <button type="button" onclick="deleteSelectedAudits()" class="text-xs bg-amber-50 border border-amber-200 hover:bg-amber-600 text-amber-700 hover:text-white px-3 py-1.5 rounded-lg font-semibold transition">
                        🗑️ Delete Marked
                    </button>
                    <button type="button" onclick="deleteAllHistoryData()" class="text-xs bg-rose-50 border border-rose-200 hover:bg-rose-600 text-rose-700 hover:text-white px-3 py-1.5 rounded-lg font-semibold transition">
                        🔥 Delete ALL
                    </button>
                    <button type="button" onclick="loadHistory(true)" class="text-xs inner-bg border border-slate-300 px-3 py-1.5 rounded-lg text-slate-700 hover:text-slate-900 transition">
                        Refresh
                    </button>
                </div>
            </div>

            <!-- Filter Controls -->
            <div class="inner-bg p-3.5 rounded-xl border border-slate-200 flex items-center gap-3 flex-wrap text-xs">
                <span class="font-bold text-sky-800 flex items-center gap-1">🔍 Filter Metric:</span>
                
                <select id="metricFilterSelect" onchange="applyMetricFilter()" class="card-bg border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-sky-600 max-w-xs">
                    <option value="ALL">-- Select Metric --</option>
                </select>

                <select id="metricFilterValue" onchange="applyMetricFilter()" class="card-bg border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-sky-600">
                    <option value="ALL">Status: ALL</option>
                    <option value="YES">YES ✅</option>
                    <option value="NO">NO ❌</option>
                </select>

                <button onclick="resetMetricFilter()" class="card-bg border border-slate-300 text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-100 transition">
                    Reset Filter
                </button>

                <button type="button" onclick="exportFilteredExcel()" class="bg-indigo-50 border border-indigo-200 text-indigo-700 hover:bg-indigo-600 hover:text-white font-semibold px-3 py-1.5 rounded-lg transition shadow-sm">
                    📥 Export Filtered
                </button>

                <span id="filterCountBadge" class="text-sub font-medium ml-auto"></span>
            </div>

            <!-- Table -->
            <div class="overflow-x-auto rounded-xl border border-slate-200">
                <table class="w-full text-left text-xs text-slate-800">
                    <thead class="inner-bg uppercase text-[10px] font-bold text-slate-600 tracking-wider border-b border-slate-200">
                        <tr>
                            <th class="p-3 text-center w-10">
                                <input type="checkbox" id="selectAllCheckbox" onchange="toggleSelectAll(this)" class="rounded border-slate-300 text-sky-600 focus:ring-0 cursor-pointer">
                            </th>
                            <th class="p-3">File Name</th>
                            <th class="p-3">Uploaded By</th>
                            <th class="p-3">Score</th>
                            <th class="p-3">Summary</th>
                            <th class="p-3">Date (IST)</th>
                            <th class="p-3 text-center">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="historyTable" class="divide-y divide-slate-100">
                        <tr><td colspan="7" class="p-4 text-center text-slate-400">Loading audit history...</td></tr>
                    </tbody>
                </table>
            </div>

            <!-- Pagination -->
            <div class="flex justify-between items-center pt-2 text-xs">
                <span id="pageInfoText" class="text-sub font-medium">Page 1 of 1</span>
                <div class="flex gap-2">
                    <button id="prevPageBtn" onclick="changePage(-1)" disabled class="inner-bg border border-slate-300 px-3 py-1.5 rounded-lg text-sub hover:text-slate-900 disabled:opacity-40 disabled:cursor-not-allowed transition">← Prev</button>
                    <button id="nextPageBtn" onclick="changePage(1)" disabled class="inner-bg border border-slate-300 px-3 py-1.5 rounded-lg text-sub hover:text-slate-900 disabled:opacity-40 disabled:cursor-not-allowed transition">Next →</button>
                </div>
            </div>
        </div>
    </div>

    <!-- METRICS MODAL -->
    <div id="metricsModal" class="fixed inset-0 bg-slate-900/40 backdrop-blur-md hidden items-center justify-center p-4 z-50">
        <div class="card-bg rounded-3xl w-full max-w-2xl p-6 space-y-6 shadow-2xl max-h-[90vh] overflow-y-auto border border-slate-200">
            <div class="flex justify-between items-center border-b border-slate-200 pb-3">
                <h3 class="text-sm font-extrabold text-sky-800 uppercase tracking-widest flex items-center gap-2">⚙️ Dynamic QA Metrics Config</h3>
                <button onclick="closeMetricModal()" class="text-sub hover:text-slate-900 font-bold text-xl px-2">&times;</button>
            </div>
            <form id="metricForm" onsubmit="saveMetric(event)" class="inner-bg p-4 rounded-2xl border border-slate-200 space-y-3">
                <input type="hidden" id="metricId" value="">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                        <label class="block text-[10px] font-bold text-sub mb-1 uppercase tracking-wider">Metric Key (Slug)</label>
                        <input type="text" id="metricKey" required placeholder="e.g. discount_offered" class="w-full card-bg border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-none focus:border-sky-600">
                    </div>
                    <div>
                        <label class="block text-[10px] font-bold text-sub mb-1 uppercase tracking-wider">Display Label</label>
                        <input type="text" id="metricLabel" required placeholder="e.g. Discount Offered" class="w-full card-bg border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-none focus:border-sky-600">
                    </div>
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-sub mb-1 uppercase tracking-wider">Evaluation Prompt Description</label>
                    <input type="text" id="metricDesc" required placeholder="e.g. Did agent offer any promotional discount?" class="w-full card-bg border border-slate-300 rounded-xl px-3 py-2 text-xs text-slate-800 focus:outline-none focus:border-sky-600">
                </div>
                <div class="flex justify-end gap-2 pt-2">
                    <button type="button" onclick="resetMetricForm()" class="card-bg border border-slate-300 text-slate-700 text-xs px-3 py-1.5 rounded-lg">Clear</button>
                    <button type="submit" class="pro-btn text-white font-bold text-xs px-4 py-1.5 rounded-lg transition">Save Metric</button>
                </div>
            </form>
            <div class="space-y-3">
                <h4 class="text-xs font-bold text-sub uppercase tracking-wider">Configured QA Metrics</h4>
                <div id="metricsListContainer" class="space-y-2"></div>
            </div>
        </div>
    </div>

    <!-- VIEW AUDIT DETAILS CUSTOM MODAL -->
    <div id="viewDetailsModal" class="fixed inset-0 bg-slate-900/40 backdrop-blur-md hidden items-center justify-center p-4 z-50">
        <div class="card-bg rounded-3xl w-full max-w-3xl p-6 space-y-5 shadow-2xl max-h-[90vh] flex flex-col border border-slate-200">
            <div class="flex justify-between items-center border-b border-slate-200 pb-3 flex-shrink-0">
                <div>
                    <h3 id="viewModalFileName" class="text-base font-bold text-sky-800">📁 Audit Details</h3>
                    <p id="viewModalMeta" class="text-xs text-sub mt-0.5"></p>
                </div>
                <button onclick="closeViewDetailsModal()" class="text-sub hover:text-slate-900 font-bold text-xl px-2">&times;</button>
            </div>
            
            <div class="space-y-4 overflow-y-auto pr-2 flex-grow">
                <div class="grid grid-cols-3 gap-3 text-center text-xs">
                    <div class="inner-bg p-3 rounded-xl border border-slate-200"><span class="text-sub block text-[10px] uppercase tracking-wider">Pace</span><span id="viewModalWPM" class="font-bold text-sky-700 text-sm">0 WPM</span></div>
                    <div class="inner-bg p-3 rounded-xl border border-slate-200"><span class="text-sub block text-[10px] uppercase tracking-wider">Duration</span><span id="viewModalDuration" class="font-bold text-indigo-700 text-sm">0s</span></div>
                    <div class="inner-bg p-3 rounded-xl border border-slate-200"><span class="text-sub block text-[10px] uppercase tracking-wider">Total Words</span><span id="viewModalWords" class="font-bold text-amber-700 text-sm">0</span></div>
                </div>

                <div class="inner-bg p-4 rounded-2xl border border-slate-200 space-y-3">
                    <div class="font-bold text-emerald-700 text-xs uppercase tracking-wider flex justify-between items-center">
                        <span>💊 Call Metrics Evaluation</span>
                        <span id="viewMetricsCount" class="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded border border-emerald-200"></span>
                    </div>
                    <div id="viewModalMetricsGrid" class="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs"></div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div class="inner-bg p-4 rounded-2xl border border-emerald-200 space-y-2">
                        <div class="font-bold text-emerald-700 uppercase tracking-wider">💪 Agent Strengths</div>
                        <ul id="viewModalStrengths" class="list-disc list-inside text-sub space-y-1"></ul>
                    </div>
                    <div class="inner-bg p-4 rounded-2xl border border-amber-200 space-y-2">
                        <div class="font-bold text-amber-700 uppercase tracking-wider">🎯 Areas for Improvement</div>
                        <ul id="viewModalImprovements" class="list-disc list-inside text-sub space-y-1"></ul>
                    </div>
                </div>

                <div class="inner-bg p-4 rounded-2xl border border-slate-200 space-y-2">
                    <div class="font-bold text-slate-900 text-xs uppercase tracking-wider">Executive Call Summary</div>
                    <p id="viewModalSummary" class="text-xs text-sub leading-relaxed whitespace-pre-wrap"></p>
                </div>

                <details class="inner-bg p-4 rounded-2xl border border-slate-200 text-xs" open>
                    <summary class="font-bold text-slate-800 cursor-pointer">📄 Full Diarized Transcript</summary>
                    <div id="viewModalTranscript" class="mt-3 space-y-2 max-h-60 overflow-y-auto pr-2 pt-2 border-t border-slate-200"></div>
                </details>
            </div>

            <div class="flex justify-end pt-2 border-t border-slate-200 flex-shrink-0">
                <button onclick="closeViewDetailsModal()" class="card-bg border border-slate-300 hover:bg-slate-100 text-slate-800 font-bold text-xs px-5 py-2 rounded-xl transition">Close</button>
            </div>
        </div>
    </div>

    <script>
        const firebaseConfig = {
          apiKey: "AIzaSyDRGZaIWz6IJvHsZrbJ1KJHXMWuc4FthV8",
          authDomain: "call-data-91e5e.firebaseapp.com",
          projectId: "call-data-91e5e",
          storageBucket: "call-data-91e5e.firebasestorage.app",
          messagingSenderId: "978960309837",
          appId: "1:978960309837:web:88edf5b11cc83c42870604",
          measurementId: "G-B3P5T684DG"
        };

        firebase.initializeApp(firebaseConfig);
        const auth = firebase.auth();

        var idToken = "";
        var currentUserName = "Admin";
        var selectedFiles = [];
        var currentBatchResults = [];
        var historyDataList = [];
        var filteredHistoryList = [];
        var activeMetrics = [];
        var currentPage = 1;
        var itemsPerPage = 10;
        var selectedAuditIds = new Set();
        
        var lastFetchTime = 0;
        var FETCH_COOL_DOWN = 30000;

        function goToHome() {
            if (auth.currentUser) {
                document.getElementById('batchResultsContainer').classList.add('hidden');
                document.getElementById('audioInput').value = "";
                document.getElementById('fileName').innerText = "Select Audio File(s) (.mp3, .wav, .m4a)";
                selectedFiles = [];
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else {
                window.location.reload();
            }
        }

        function extractDuration(item) {
            return Math.round(item.duration ?? item.data?.metrics?.duration ?? 0);
        }

        function extractTotalWords(item) {
            return item.total_words ?? item.data?.metrics?.total_words ?? 0;
        }

        function extractWPM(item) {
            return item.wpm ?? item.data?.metrics?.wpm ?? 0;
        }

        function buildExcelRow(item, isBatchResult = false) {
            var fileName = isBatchResult ? item.filename : (item.filename || "N/A");
            var uName = isBatchResult ? currentUserName : (item.uploaded_by || currentUserName || "Admin");
            var score = isBatchResult ? (item.data?.evaluation?.overall_score || 0) : (item.score || 0);
            var summary = isBatchResult ? (item.data?.evaluation?.summary || "") : (item.summary || "");
            var createdAt = isBatchResult ? formatDateDisplay(new Date().toISOString()) : formatDateDisplay(item.created_at);
            
            var strengthsList = isBatchResult ? (item.data?.evaluation?.strengths || []) : (item.strengths || []);
            var improvementsList = isBatchResult ? (item.data?.evaluation?.improvements || []) : (item.improvements || []);

            var formattedStrengths = strengthsList.length > 0 ? strengthsList.map(s => "• " + s).join("<br/>") : "None";
            var formattedImprovements = improvementsList.length > 0 ? improvementsList.map(i => "• " + i).join("<br/>") : "None";

            var row = {
                "File Name": fileName,
                "Uploaded By": uName,
                "QA Score": score,
                "WPM": extractWPM(item),
                "Duration (sec)": extractDuration(item),
                "Total Words": extractTotalWords(item),
                "Date & Time (IST)": createdAt,
                "Strengths": formattedStrengths,
                "Areas for Improvement": formattedImprovements,
                "Summary": summary
            };

            var evalMetrics = isBatchResult ? (item.data?.evaluation?.evaluated_metrics || {}) : (item.evaluated_metrics || {});

            activeMetrics.forEach(m => {
                if (evalMetrics.hasOwnProperty(m.key)) {
                    row[m.label] = (evalMetrics[m.key] === true) ? "YES" : "NO";
                } else {
                    row[m.label] = "N/A";
                }
            });

            return row;
        }

        function exportMultiSheetExcel(rawItemsList, fileName, isBatchResult = false) {
            if (!rawItemsList || rawItemsList.length === 0) return alert("No data to export!");

            var totalCalls = rawItemsList.length;
            var validItems = isBatchResult ? rawItemsList.filter(i => i.status === "success") : rawItemsList;
            
            var metricStats = [];
            var avgScore = 0;
            var totalScore = 0;

            validItems.forEach(i => {
                var score = isBatchResult ? (i.data?.evaluation?.overall_score || 0) : (i.score || 0);
                totalScore += score;
            });

            avgScore = totalCalls > 0 ? Math.round(totalScore / totalCalls) : 0;

            activeMetrics.forEach(m => {
                var yesCount = 0;
                validItems.forEach(i => {
                    var evalMetrics = isBatchResult ? (i.data?.evaluation?.evaluated_metrics || {}) : (i.evaluated_metrics || {});
                    if (evalMetrics[m.key] === true) yesCount++;
                });

                var pct = totalCalls > 0 ? Math.round((yesCount / totalCalls) * 100) : 0;
                
                var filledBars = Math.round(pct / 10);
                var emptyBars = 10 - filledBars;
                var visualChart = "█".repeat(filledBars) + "░".repeat(emptyBars) + ` ${pct}%`;

                metricStats.push({
                    "Evaluated Metric": m.label,
                    "Total Yes / Positive": yesCount,
                    "Total Calls Analyzed": totalCalls,
                    "Success %": pct + "%",
                    "Visual Performance Graph": visualChart
                });
            });

            var dashboardHtml = `<table border="1">
                <thead>
                    <tr><th colspan="5" style="text-align:center; vertical-align:middle; background-color:#0284c7; color:#ffffff; font-weight:bold; font-size:16px; padding:10px;">📊 AI AUDIT BATCH ANALYTICS & METRIC DASHBOARD</th></tr>
                    <tr>
                        <th style="text-align:center; background-color:#f1f5f9; color:#0f172a;">KPI Metric Name</th>
                        <th style="text-align:center; background-color:#f1f5f9; color:#0f172a;">Positive Count</th>
                        <th style="text-align:center; background-color:#f1f5f9; color:#0f172a;">Total Calls</th>
                        <th style="text-align:center; background-color:#f1f5f9; color:#0f172a;">Conversion %</th>
                        <th style="text-align:center; background-color:#f1f5f9; color:#0f172a;">Visual Graph Bar</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="text-align:center; font-weight:bold; background-color:#0284c7; color:#ffffff;">Average Call Quality Score</td>
                        <td style="text-align:center; font-weight:bold; background-color:#0284c7; color:#ffffff;" colspan="2">${avgScore} / 100</td>
                        <td style="text-align:center; font-weight:bold; background-color:#0284c7; color:#ffffff;" colspan="2">${avgScore}% Overall Quality Index</td>
                    </tr>`;

            metricStats.forEach(stat => {
                dashboardHtml += `<tr>
                    <td style="text-align:center; vertical-align:middle; font-weight:bold;">${stat["Evaluated Metric"]}</td>
                    <td style="text-align:center; vertical-align:middle;">${stat["Total Yes / Positive"]}</td>
                    <td style="text-align:center; vertical-align:middle;">${stat["Total Calls Analyzed"]}</td>
                    <td style="text-align:center; vertical-align:middle; font-weight:bold; color:#10b981;">${stat["Success %"]}</td>
                    <td style="text-align:center; vertical-align:middle; font-weight:bold; font-family:monospace; color:#0284c7;">${stat["Visual Performance Graph"]}</td>
                </tr>`;
            });

            dashboardHtml += '</tbody></table>';

            var rawRows = rawItemsList.map(item => buildExcelRow(item, isBatchResult));
            var rawKeys = Object.keys(rawRows[0]);

            var detailsHtml = '<table border="1"><thead><tr>';
            rawKeys.forEach(k => {
                detailsHtml += `<th style="text-align: center; vertical-align: middle; background-color: #f1f5f9; color: #0f172a; font-weight: bold; padding: 8px;">${k}</th>`;
            });
            detailsHtml += '</tr></thead><tbody>';

            rawRows.forEach(row => {
                detailsHtml += '<tr>';
                rawKeys.forEach(k => {
                    var val = row[k] !== undefined && row[k] !== null ? row[k] : "";
                    detailsHtml += `<td style="text-align: center; vertical-align: middle; padding: 6px; mso-number-format:'\@';">${val}</td>`;
                });
                detailsHtml += '</tr>';
            });
            detailsHtml += '</tbody></table>';

            var parser = new DOMParser();
            var workbook = XLSX.utils.book_new();

            var dashSheet = XLSX.utils.table_to_sheet(parser.parseFromString(dashboardHtml, 'text/html').body.getElementsByTagName('table')[0], { raw: true });
            dashSheet["!cols"] = [{ wch: 32 }, { wch: 16 }, { wch: 16 }, { wch: 16 }, { wch: 32 }];
            XLSX.utils.book_append_sheet(workbook, dashSheet, "📌 Dashboard Analytics");

            var detailSheet = XLSX.utils.table_to_sheet(parser.parseFromString(detailsHtml, 'text/html').body.getElementsByTagName('table')[0], { raw: true });
            var detailWidths = rawKeys.map(key => {
                var maxLen = key.length;
                rawRows.forEach(r => {
                    var v = r[key] ? r[key].toString() : "";
                    if (v.length > maxLen) maxLen = v.length;
                });
                return { wch: Math.min(Math.max(maxLen + 4, 14), 30) };
            });
            detailSheet["!cols"] = detailWidths;
            XLSX.utils.book_append_sheet(workbook, detailSheet, "📁 Individual Call Details");

            XLSX.writeFile(workbook, fileName);
        }

        auth.onAuthStateChanged(async (user) => {
            var loader = document.getElementById('initialAppLoader');
            var authModal = document.getElementById('authModal');
            var dashContent = document.getElementById('dashboardContent');

            if (user) {
                idToken = await user.getIdToken(true);
                currentUserName = user.displayName || (user.email ? user.email.split('@')[0] : "Admin");
                document.getElementById('userDisplayName').innerText = currentUserName;

                if (authModal) {
                    authModal.classList.add('hidden');
                    authModal.classList.remove('flex');
                }
                if (dashContent) dashContent.classList.remove('hidden');
                
                if (loader) loader.classList.add('hidden');
                
                await fetchMetrics();
                loadHistory();
            } else {
                idToken = "";
                if (dashContent) dashContent.classList.add('hidden');
                if (authModal) {
                    authModal.classList.remove('hidden');
                    authModal.classList.add('flex');
                }
                
                if (loader) loader.classList.add('hidden');
            }
        });

        async function handleLogin(e) {
            e.preventDefault();
            const email = document.getElementById('adminEmail').value.trim();
            const password = document.getElementById('adminPassword').value.trim();
            const errorDiv = document.getElementById('authError');
            const loginBtn = document.getElementById('loginBtn');
            
            try {
                errorDiv.classList.add('hidden');
                loginBtn.innerText = "AUTHENTICATING...";
                await auth.signInWithEmailAndPassword(email, password);
            } catch (error) {
                errorDiv.innerText = error.message;
                errorDiv.classList.remove('hidden');
            } finally {
                loginBtn.innerText = "AUTHENTICATE";
            }
        }

        function handleLogout() { auth.signOut(); }

        async function fetchAuth(url, options = {}) {
            if (!options.headers) options.headers = {};
            if (auth.currentUser) {
                idToken = await auth.currentUser.getIdToken(true);
            }
            options.headers['Authorization'] = 'Bearer ' + idToken;
            return fetch(url, options);
        }

        function formatDateDisplay(dateStr) {
            if(!dateStr) return "N/A";
            try {
                const date = new Date(dateStr);
                if(isNaN(date.getTime())) return dateStr;
                return date.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
            } catch(e) { return dateStr; }
        }

        async function fetchMetrics() {
            try {
                var res = await fetchAuth("/api/metrics");
                activeMetrics = await res.json();
                renderMetricsList();
                populateMetricFilterDropdown();
            } catch(e) { console.error(e); }
        }

        function populateMetricFilterDropdown() {
            var select = document.getElementById('metricFilterSelect');
            if(!select) return;
            select.innerHTML = '<option value="ALL">-- Select Metric --</option>';
            activeMetrics.forEach(m => {
                select.innerHTML += `<option value="${m.key}">${m.label}</option>`;
            });
        }

        function renderMetricsList() {
            var container = document.getElementById('metricsListContainer');
            if (!activeMetrics || activeMetrics.length === 0) {
                container.innerHTML = '<div class="text-xs text-sub text-center py-2">No metrics defined.</div>';
                return;
            }
            var html = '';
            activeMetrics.forEach(function(m) {
                html += `
                <div class="inner-bg p-3.5 rounded-xl border border-slate-200 flex justify-between items-center text-xs">
                    <div>
                        <span class="font-bold text-sky-800">${m.label}</span>
                        <span class="text-sub text-[10px] ml-2">(${m.key})</span>
                        <p class="text-sub text-[11px] mt-0.5">${m.description}</p>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="editMetric('${m.id}')" class="text-sky-700 hover:text-sky-900 bg-sky-100 px-2.5 py-1 rounded-md transition font-semibold">Edit</button>
                        <button onclick="deleteMetric('${m.id}')" class="text-rose-700 hover:text-rose-900 bg-rose-100 px-2.5 py-1 rounded-md transition font-semibold">Delete</button>
                    </div>
                </div>`;
            });
            container.innerHTML = html;
        }

        function openMetricModal() {
            document.getElementById('metricsModal').classList.remove('hidden');
            document.getElementById('metricsModal').classList.add('flex');
            fetchMetrics();
        }

        function closeMetricModal() {
            document.getElementById('metricsModal').classList.add('hidden');
            document.getElementById('metricsModal').classList.remove('flex');
            resetMetricForm();
        }

        function resetMetricForm() {
            document.getElementById('metricId').value = "";
            document.getElementById('metricKey').value = "";
            document.getElementById('metricLabel').value = "";
            document.getElementById('metricDesc').value = "";
            document.getElementById('metricKey').disabled = false;
        }

        function editMetric(id) {
            var m = activeMetrics.find(x => x.id === id);
            if (!m) return;
            document.getElementById('metricId').value = m.id;
            document.getElementById('metricKey').value = m.key;
            document.getElementById('metricKey').disabled = true;
            document.getElementById('metricLabel').value = m.label;
            document.getElementById('metricDesc').value = m.description;
        }

        async function saveMetric(e) {
            e.preventDefault();
            var id = document.getElementById('metricId').value;
            var payload = {
                key: document.getElementById('metricKey').value.trim(),
                label: document.getElementById('metricLabel').value.trim(),
                description: document.getElementById('metricDesc').value.trim()
            };
            var url = id ? `/api/metrics/${id}` : '/api/metrics';
            var method = id ? 'PUT' : 'POST';

            try {
                var res = await fetchAuth(url, { method: method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
                if(!res.ok) throw new Error("Failed to save metric");
                resetMetricForm();
                await fetchMetrics();
            } catch(err) { alert("Error: " + err.message); }
        }

        async function deleteMetric(id) {
            if(!confirm("Are you sure?")) return;
            try {
                var res = await fetchAuth(`/api/metrics/${id}`, { method: 'DELETE' });
                if(!res.ok) throw new Error("Failed");
                await fetchMetrics();
            } catch(err) { alert("Error: " + err.message); }
        }

        function fileSelected(e) {
            selectedFiles = Array.from(e.target.files);
            if(selectedFiles.length > 0) {
                document.getElementById('fileName').innerText = selectedFiles.length + " audio file(s) ready for analysis";
            }
        }

        async function uploadAudioBatch() {
            if (selectedFiles.length === 0) return alert("Select audio file!");
            document.getElementById('progressContainer').classList.remove('hidden');
            document.getElementById('batchResultsContainer').classList.remove('hidden');
            
            currentBatchResults = [];
            const totalFiles = selectedFiles.length;
            const CHUNK_SIZE = 3;
            let completedCount = 0;

            for (let i = 0; i < totalFiles; i += CHUNK_SIZE) {
                const chunk = selectedFiles.slice(i, i + CHUNK_SIZE);
                const formData = new FormData();
                chunk.forEach(file => formData.append("files", file));

                try {
                    const res = await fetchAuth("/api/analyze-batch", { method: "POST", body: formData });
                    const batchData = await res.json();
                    if (res.ok && batchData.results) {
                        currentBatchResults.push(...batchData.results);
                        renderBatchResults(currentBatchResults);
                    }
                } catch (err) { console.error(err); }

                completedCount += chunk.length;
                const progressPct = Math.round((completedCount / totalFiles) * 100);
                document.getElementById('progressBar').style.width = progressPct + "%";
                document.getElementById('loaderText').innerText = `⚡ Auditing... ${completedCount} / ${totalFiles} (${progressPct}%)`;
            }

            setTimeout(() => { document.getElementById('progressContainer').classList.add('hidden'); }, 2000);
            setTimeout(() => loadHistory(true), 1000);
        }

        function renderBatchResults(results) {
            var container = document.getElementById('resultsList');
            container.innerHTML = "";
            var validResults = results.filter(r => r.status === "success");
            var totalCalls = validResults.length;
            var metricCounts = {};
            activeMetrics.forEach(m => metricCounts[m.key] = 0);

            validResults.forEach(item => {
                var evalMetrics = item.data?.evaluation?.evaluated_metrics || {};
                activeMetrics.forEach(m => {
                    if(evalMetrics[m.key]) metricCounts[m.key] = (metricCounts[m.key] || 0) + 1;
                });
            });

            function calcPct(val) { return totalCalls === 0 ? "0%" : Math.round((val / totalCalls) * 100) + "%"; }

            document.getElementById('totalCallsBadge').innerText = "Total Calls: " + totalCalls;
            document.getElementById('summaryTimeSlot').innerText = "Audit Generated: " + new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });

            var summaryHtml = `<tr class="hover:bg-slate-50"><td class="p-3 font-semibold text-slate-800">Total Calls Reviewed</td><td class="p-3 text-center font-bold text-sky-700">${totalCalls}</td><td class="p-3 text-center font-extrabold text-emerald-600">100%</td></tr>`;
            activeMetrics.forEach(m => {
                var cnt = metricCounts[m.key] || 0;
                summaryHtml += `<tr class="hover:bg-slate-50"><td class="p-3 font-medium text-slate-700">${m.label}</td><td class="p-3 text-center font-bold text-sky-700">${cnt}</td><td class="p-3 text-center font-bold text-emerald-600">${calcPct(cnt)}</td></tr>`;
            });
            document.getElementById('summaryTableBody').innerHTML = summaryHtml;

            results.forEach(item => {
                if(item.status !== "success") {
                    container.innerHTML += `<div class="bg-rose-50 border border-rose-200 p-4 rounded-xl text-rose-700 text-xs">❌ Failed to audit: ${item.filename}</div>`;
                    return;
                }
                var data = item.data || {};
                var evalData = data.evaluation || {};
                var evalMetrics = evalData.evaluated_metrics || {};
                var transcript = data.transcript || [];
                var strengths = evalData.strengths || [];
                var improvements = evalData.improvements || [];
                
                var card = document.createElement('div');
                card.className = "card-bg rounded-2xl p-6 shadow-md space-y-4 border border-slate-200";
                
                var transcriptHtml = "";
                transcript.forEach(t => {
                    var colorClass = t.speaker === 'Agent' ? 'text-sky-700 font-semibold' : 'text-emerald-700 font-semibold';
                    transcriptHtml += `<div class="mb-1.5"><b class="${colorClass}">${t.speaker}:</b> ${t.text}</div>`;
                });

                var dynamicCardsHtml = '';
                activeMetrics.forEach(m => {
                    var fmt = evalMetrics[m.key] ? '<span class="text-emerald-700 font-bold ml-1">YES</span>' : '<span class="text-rose-600 font-bold ml-1">NO</span>';
                    dynamicCardsHtml += `<div class="inner-bg p-2 rounded-lg border border-slate-200">${m.label}:${fmt}</div>`;
                });

                var strengthsHtml = strengths.length > 0 ? strengths.map(s => `<li>${s}</li>`).join('') : '<li class="italic">None listed</li>';
                var improvementsHtml = improvements.length > 0 ? improvements.map(i => `<li>${i}</li>`).join('') : '<li class="italic">None listed</li>';

                card.innerHTML = `
                    <div class="flex justify-between items-center border-b border-slate-200 pb-3">
                        <h3 class="font-bold text-sky-800 text-sm flex items-center gap-2">📁 ${item.filename}</h3>
                        <span class="text-emerald-700 font-extrabold text-lg bg-emerald-50 px-3 py-0.5 rounded-full border border-emerald-200">${evalData.overall_score || 0}/100</span>
                    </div>
                    <div class="grid grid-cols-3 gap-2 text-center text-xs">
                        <div class="inner-bg p-2.5 rounded-xl border border-slate-200"><span class="text-sub block text-[10px] uppercase">PACE</span><span class="font-bold text-sky-700">${extractWPM(item)} WPM</span></div>
                        <div class="inner-bg p-2.5 rounded-xl border border-slate-200"><span class="text-sub block text-[10px] uppercase">DURATION</span><span class="font-bold text-indigo-700">${extractDuration(item)}s</span></div>
                        <div class="inner-bg p-2.5 rounded-xl border border-slate-200"><span class="text-sub block text-[10px] uppercase">WORDS</span><span class="font-bold text-amber-700">${extractTotalWords(item)}</span></div>
                    </div>
                    <div class="inner-bg p-4 rounded-2xl border border-slate-200 space-y-2">
                        <div class="font-bold text-emerald-700 text-[11px] uppercase tracking-wider">💊 Call Metrics Evaluation</div>
                        <div class="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">${dynamicCardsHtml}</div>
                    </div>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                        <div class="inner-bg p-4 rounded-2xl border border-emerald-200 space-y-1.5">
                            <div class="font-bold text-emerald-700 text-[11px] uppercase tracking-wider">💪 Agent Strengths</div>
                            <ul class="list-disc list-inside text-sub space-y-0.5">${strengthsHtml}</ul>
                        </div>
                        <div class="inner-bg p-4 rounded-2xl border border-amber-200 space-y-1.5">
                            <div class="font-bold text-amber-700 text-[11px] uppercase tracking-wider">🎯 Areas for Improvement</div>
                            <ul class="list-disc list-inside text-sub space-y-0.5">${improvementsHtml}</ul>
                        </div>
                    </div>

                    <div class="text-xs inner-bg p-4 rounded-2xl border border-slate-200 space-y-1">
                        <div class="font-bold text-slate-800 text-[11px] uppercase tracking-wider">Executive Call Summary</div>
                        <p class="text-sub leading-relaxed">${evalData.summary || "N/A"}</p>
                    </div>
                    <details class="inner-bg p-4 rounded-2xl border border-slate-200 text-xs">
                        <summary class="font-bold text-slate-800 cursor-pointer">📄 Full Diarized Transcript</summary>
                        <div class="mt-3 space-y-2 max-h-48 overflow-y-auto pr-2 pt-2 border-t border-slate-200">${transcriptHtml}</div>
                    </details>`;
                container.appendChild(card);
            });
        }

        async function loadHistory(forceRefresh = false) {
            var now = Date.now();
            if (!forceRefresh && historyDataList.length > 0 && (now - lastFetchTime < FETCH_COOL_DOWN)) {
                renderHistoryTable();
                return;
            }

            var hTable = document.getElementById('historyTable');
            try {
                if (!auth.currentUser) return;
                idToken = await auth.currentUser.getIdToken(true);
                var url = forceRefresh ? "/api/history?refresh=true" : "/api/history";
                var res = await fetchAuth(url);
                if(!res.ok) throw new Error("HTTP error " + res.status);
                var list = await res.json();
                historyDataList = list || [];
                lastFetchTime = Date.now();
                
                selectedAuditIds.clear();
                document.getElementById('selectAllCheckbox').checked = false;
                document.getElementById('totalHistoryBadge').innerText = historyDataList.length + " Records";
                
                updateSelectedCounter();
                applyMetricFilter();
            } catch(e) {
                hTable.innerHTML = '<tr><td colspan="7" class="p-4 text-center text-rose-600">Failed to load history records.</td></tr>';
            }
        }

        function applyMetricFilter() {
            var selectedMetricKey = document.getElementById('metricFilterSelect').value;
            var selectedValue = document.getElementById('metricFilterValue').value;

            if (selectedMetricKey === "ALL") {
                filteredHistoryList = [...historyDataList];
                document.getElementById('filterCountBadge').innerText = "";
            } else {
                filteredHistoryList = historyDataList.filter(item => {
                    var evalMetrics = item.evaluated_metrics || {};
                    if (!evalMetrics.hasOwnProperty(selectedMetricKey)) return false;

                    var metricVal = evalMetrics[selectedMetricKey];
                    if (selectedValue === "YES") return metricVal === true;
                    if (selectedValue === "NO") return metricVal === false;
                    return true;
                });
                document.getElementById('filterCountBadge').innerText = `Showing ${filteredHistoryList.length} of ${historyDataList.length} items`;
            }

            currentPage = 1;
            renderHistoryTable();
        }

        function resetMetricFilter() {
            document.getElementById('metricFilterSelect').value = "ALL";
            document.getElementById('metricFilterValue').value = "ALL";
            applyMetricFilter();
        }

        function renderHistoryTable() {
            var hTable = document.getElementById('historyTable');
            var dataToRender = filteredHistoryList || [];

            if(!dataToRender || dataToRender.length === 0) {
                hTable.innerHTML = '<tr><td colspan="7" class="p-4 text-center text-slate-400">No audits found for selected filter.</td></tr>';
                document.getElementById('pageInfoText').innerText = "Page 0 of 0";
                document.getElementById('prevPageBtn').disabled = true;
                document.getElementById('nextPageBtn').disabled = true;
                return;
            }

            var totalPages = Math.ceil(dataToRender.length / itemsPerPage);
            if(currentPage > totalPages) currentPage = totalPages;
            if(currentPage < 1) currentPage = 1;

            var startIndex = (currentPage - 1) * itemsPerPage;
            var pageItems = dataToRender.slice(startIndex, startIndex + itemsPerPage);

            hTable.innerHTML = "";
            pageItems.forEach((item, index) => {
                var globalIndex = startIndex + index;
                var isChecked = selectedAuditIds.has(item.id) ? "checked" : "";
                
                var uploadedUser = item.uploaded_by;
                if (!uploadedUser || uploadedUser === "Unknown") {
                    uploadedUser = currentUserName || "Admin";
                }
                
                hTable.innerHTML += `
                    <tr class="hover:bg-slate-50 transition">
                        <td class="p-3 text-center">
                            <input type="checkbox" value="${item.id}" ${isChecked} onchange="toggleAuditSelect('${item.id}', this)" class="row-checkbox rounded border-slate-300 text-sky-600 focus:ring-0 cursor-pointer">
                        </td>
                        <td class="p-3 font-semibold text-slate-800">${item.filename || 'N/A'}</td>
                        <td class="p-3 font-medium text-indigo-700">👤 ${uploadedUser}</td>
                        <td class="p-3"><span class="bg-emerald-50 text-emerald-700 border border-emerald-200 font-extrabold px-2.5 py-0.5 rounded-full">${item.score || 0}/100</span></td>
                        <td class="p-3 text-sub max-w-xs truncate">${item.summary || 'N/A'}</td>
                        <td class="p-3 text-sub">${formatDateDisplay(item.created_at)}</td>
                        <td class="p-3 text-center">
                            <div class="flex items-center justify-center gap-1.5">
                                <button onclick="viewHistoryDetails(${globalIndex})" title="View Details" class="bg-sky-50 text-sky-700 border border-sky-200 hover:bg-sky-600 hover:text-white px-2.5 py-1 rounded-md font-semibold transition">
                                    👁️ View
                                </button>
                                <button onclick="downloadSingleHistoryExcel(${globalIndex})" title="Export Excel" class="bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-600 hover:text-white px-2.5 py-1 rounded-md font-semibold transition">
                                    📊 Excel
                                </button>
                                <button onclick="deleteHistoryItem('${item.id}', ${globalIndex})" title="Delete Audit" class="bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-600 hover:text-white px-2.5 py-1 rounded-md font-semibold transition">
                                    🗑️ Delete
                                </button>
                            </div>
                        </td>
                    </tr>`;
            });

            document.getElementById('pageInfoText').innerText = `Page ${currentPage} of ${totalPages} (${dataToRender.length} items)`;
            document.getElementById('prevPageBtn').disabled = currentPage === 1;
            document.getElementById('nextPageBtn').disabled = currentPage === totalPages;
        }

        function changePage(direction) { currentPage += direction; renderHistoryTable(); }

        function updateSelectedCounter() {
            var count = selectedAuditIds.size;
            var badge = document.getElementById('selectedCountBadge');
            if(badge) {
                badge.innerText = "Selected: " + count;
                if(count > 0) {
                    badge.classList.remove('bg-emerald-50', 'text-emerald-700', 'border-emerald-200');
                    badge.classList.add('bg-sky-600', 'text-white', 'border-sky-600');
                } else {
                    badge.classList.remove('bg-sky-600', 'text-white', 'border-sky-600');
                    badge.classList.add('bg-emerald-50', 'text-emerald-700', 'border-emerald-200');
                }
            }
        }

        function toggleSelectAll(masterCheckbox) {
            var checkboxes = document.querySelectorAll('.row-checkbox');
            checkboxes.forEach(cb => {
                cb.checked = masterCheckbox.checked;
                if(masterCheckbox.checked) {
                    selectedAuditIds.add(cb.value);
                } else {
                    selectedAuditIds.delete(cb.value);
                }
            });
            updateSelectedCounter();
        }

        function toggleAuditSelect(id, checkbox) {
            if(checkbox.checked) {
                selectedAuditIds.add(id);
            } else {
                selectedAuditIds.delete(id);
                document.getElementById('selectAllCheckbox').checked = false;
            }
            updateSelectedCounter();
        }

        // ================= FULL DATABASE EXPORT =================
        async function exportHistoryExcel(evt) {
            var btn = evt ? (evt.target || document.getElementById('exportAllBtn')) : document.getElementById('exportAllBtn');
            var originalText = btn ? btn.innerText : "📊 Export ALL Data to Excel";
            if (btn) btn.innerText = "⏳ Fetching Complete Database...";

            try {
                if (auth.currentUser) {
                    idToken = await auth.currentUser.getIdToken(true);
                }
                var res = await fetchAuth("/api/history?limit=0&refresh=true");
                if (!res.ok) throw new Error("Failed to fetch full history data");
                var allDbData = await res.json();

                if (!allDbData || allDbData.length === 0) {
                    if (btn) btn.innerText = originalText;
                    return alert("Database me koi record nahi mila!");
                }

                exportMultiSheetExcel(allDbData, `Complete_Database_Export_${allDbData.length}_Records.xlsx`, false);
                if (btn) btn.innerText = originalText;
            } catch (err) {
                alert("Export error: " + err.message);
                if (btn) btn.innerText = originalText;
            }
        }

        function exportSelectedExcel() {
            if(selectedAuditIds.size === 0) {
                return alert("Pehle items mark/select karein!");
            }

            var targetItems = historyDataList.filter(item => selectedAuditIds.has(item.id));
            if(targetItems.length === 0) return alert("Selected records local view me nahi mile!");

            exportMultiSheetExcel(targetItems, `Selected_Audits_Export_${targetItems.length}.xlsx`, false);
        }

        async function deleteSelectedAudits() {
            if(selectedAuditIds.size === 0) {
                return alert("Pehle delete karne ke liye records mark/select karein!");
            }

            if(!confirm(`Kya aap sach me selected (${selectedAuditIds.size}) records ko Firestore se permanent delete karna chahte hain?`)) {
                return;
            }

            var idsToDelete = Array.from(selectedAuditIds);
            var successCount = 0;

            for(let id of idsToDelete) {
                try {
                    var res = await fetchAuth(`/api/history/${id}`, { method: 'DELETE' });
                    if(res.ok) successCount++;
                } catch(e) { console.error(e); }
            }

            alert(`${successCount} / ${idsToDelete.length} records successfully delete ho gaye!`);
            await loadHistory(true);
        }

        function exportFilteredExcel() {
            var targetItems = filteredHistoryList || [];
            if(targetItems.length === 0) {
                return alert("Export karne ke liye koi filtered data nahi mila!");
            }

            exportMultiSheetExcel(targetItems, `Filtered_Audits_Export_${targetItems.length}.xlsx`, false);
        }

        async function deleteAllHistoryData() {
            if(!historyDataList || historyDataList.length === 0) {
                return alert("Pehle se hi koi record nahi hai!");
            }

            if(!confirm(`⚠️ WARNING: Kya aap SACH ME POORA DATABASE DELETE karna chahte hain?\n\nTotal Records: ${historyDataList.length}\n\nYeh action undo nahi ho sakta!`)) {
                return;
            }

            try {
                var res = await fetchAuth("/api/history/delete-all", { method: 'DELETE' });
                if(!res.ok) throw new Error("Failed to delete all data");
                var resData = await res.json();
                alert(`🔥 Success: ${resData.deleted_count} records permanently delete ho gaye!`);
                await loadHistory(true);
            } catch(err) {
                alert("Error deleting all data: " + err.message);
            }
        }

        function viewHistoryDetails(index) {
            var item = filteredHistoryList[index];
            if(!item) return;

            var evalMetrics = item.evaluated_metrics || {};
            var uName = item.uploaded_by || currentUserName || 'Admin';

            document.getElementById('viewModalFileName').innerText = "📁 " + (item.filename || "Audit Details");
            document.getElementById('viewModalMeta').innerText = `👤 Uploaded By: ${uName} | ⭐ Score: ${item.score || 0}/100 | Date: ${formatDateDisplay(item.created_at)}`;
            
            document.getElementById('viewModalWPM').innerText = extractWPM(item) + " WPM";
            document.getElementById('viewModalDuration').innerText = extractDuration(item) + "s";
            document.getElementById('viewModalWords').innerText = extractTotalWords(item);

            document.getElementById('viewModalSummary').innerText = item.summary || "No summary available.";

            var strengthsList = item.strengths || [];
            var improvementsList = item.improvements || [];

            var strengthsContainer = document.getElementById('viewModalStrengths');
            var improvementsContainer = document.getElementById('viewModalImprovements');

            strengthsContainer.innerHTML = strengthsList.length > 0 
                ? strengthsList.map(s => `<li>${s}</li>`).join('') 
                : '<li class="italic">None listed</li>';

            improvementsContainer.innerHTML = improvementsList.length > 0 
                ? improvementsList.map(i => `<li>${i}</li>`).join('') 
                : '<li class="italic">None listed</li>';

            var gridContainer = document.getElementById('viewModalMetricsGrid');
            gridContainer.innerHTML = "";

            var metricKeysSet = new Set([
                ...activeMetrics.map(m => m.key),
                ...Object.keys(evalMetrics)
            ]);

            var metricsCount = 0;
            metricKeysSet.forEach(key => {
                var metricDef = activeMetrics.find(m => m.key === key);
                var label = metricDef ? metricDef.label : key;

                var fmt = "";
                if (evalMetrics.hasOwnProperty(key)) {
                    fmt = (evalMetrics[key] === true) 
                        ? '<span class="text-emerald-700 font-bold ml-1">YES</span>' 
                        : '<span class="text-rose-600 font-bold ml-1">NO</span>';
                } else {
                    fmt = '<span class="text-slate-500 font-bold ml-1">N/A</span>';
                }

                gridContainer.innerHTML += `<div class="inner-bg p-2 rounded-lg border border-slate-200">${label}:${fmt}</div>`;
                metricsCount++;
            });

            document.getElementById('viewMetricsCount').innerText = `${metricsCount} Metrics Evaluated`;

            var transcriptContainer = document.getElementById('viewModalTranscript');
            transcriptContainer.innerHTML = "";

            var transcriptList = item.transcript || [];
            if (transcriptList.length === 0) {
                transcriptContainer.innerHTML = '<div class="text-sub italic">No transcript recorded or stored for this call.</div>';
            } else {
                transcriptList.forEach(t => {
                    var colorClass = t.speaker === 'Agent' ? 'text-sky-700 font-semibold' : 'text-emerald-700 font-semibold';
                    transcriptContainer.innerHTML += `<div class="mb-1.5"><b class="${colorClass}">${t.speaker}:</b> ${t.text}</div>`;
                });
            }

            var modal = document.getElementById('viewDetailsModal');
            modal.classList.remove('hidden');
            modal.classList.add('flex');
        }

        function closeViewDetailsModal() {
            var modal = document.getElementById('viewDetailsModal');
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        }

        function downloadSingleHistoryExcel(index) {
            var item = filteredHistoryList[index];
            if(!item) return;

            exportMultiSheetExcel([item], `${item.filename || 'Single'}_Audit.xlsx`, false);
        }

        async function deleteHistoryItem(auditId, index) {
            if(!auditId) {
                alert("Cannot delete this record (Missing Document ID).");
                return;
            }
            
            if(!confirm("Kya aap sach me is audit record ko Firestore se delete karna chahte hain?")) {
                return;
            }

            try {
                var res = await fetchAuth(`/api/history/${auditId}`, { method: 'DELETE' });
                if(!res.ok) throw new Error("Delete failed on server side.");

                await loadHistory(true);
                alert("Record deleted successfully!");
            } catch(err) {
                alert("Error deleting record: " + err.message);
            }
        }

        function downloadExcel() {
            if(!currentBatchResults || currentBatchResults.length === 0) return alert("No data!");
            
            exportMultiSheetExcel(currentBatchResults, "Detailed_Call_Audit_Report.xlsx", true);
        }

        function downloadPDF() {
            var element = document.getElementById('batchResultsContainer');
            html2pdf().from(element).save("Batch_Call_Audit_Report.pdf");
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return HTML_CONTENT

@app.get("/ai.html", response_class=HTMLResponse)
async def serve_ai_page():
    if os.path.exists("ai.html"):
        with open("ai.html", "r", encoding="utf-8") as f:
            return f.read()
    else:
        return HTMLResponse("<h1>ai.html File missing in project root folder!</h1>", status_code=404)

# ================= Groq Audio Transcribe & Diarize API =================

@app.post("/api/groq-transcribe-eval")
async def groq_transcribe_eval(
    file: UploadFile = File(...),
    user: dict = Depends(verify_firebase_token)
):
    if not GROQ_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GROQ_API_KEY environment variable missing on Render server!"
        )

    try:
        audio_bytes = await file.read()
        filename = file.filename
        content_type = file.content_type or "audio/mpeg"

        async with httpx.AsyncClient(timeout=300.0) as client:
            files_payload = {"file": (filename, audio_bytes, content_type)}
            data_payload = {
                "model": "whisper-large-v3",
                "language": "hi",
                "temperature": "0",
                "response_format": "json",
                "prompt": "यह एक कॉल सेंटर सपोर्ट कॉल है। Agent aur Customer ke shuruat se ant tak ki saari baat ko bina kisi shabd ko chhode poora transcribe karein."
            }
            
            whisper_res = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files=files_payload,
                data=data_payload
            )

            if whisper_res.status_code != 200:
                raise Exception(f"Groq Whisper Error ({whisper_res.status_code}): {whisper_res.text}")

            raw_transcript = whisper_res.json().get("text", "").strip()

            llm_prompt = f"""
You are an expert Call Center QA Auditor.
Below is a full raw transcript of a customer service call in Hindi/Hinglish/English:

"{raw_transcript}"

TASKS:
1. Parse the transcript from START TO END and divide it into chronological dialogue turns between "Agent:" and "Customer:".
2. Make sure NO PART of the conversation from start to end is omitted or summarized.
3. Output ONLY a JSON object with this exact structure:
{{
  "full_diarized_transcript": "Agent: [dialogue]\\nCustomer: [dialogue]\\nAgent: [dialogue]",
  "agent_only_speech": "Combined string of everything the Agent said from start to end"
}}
Do not include markdown or explanations outside the valid JSON.
"""
            llm_res = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": llm_prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1
                }
            )

            if llm_res.status_code != 200:
                return {
                    "full_diarized_transcript": raw_transcript,
                    "agent_only_speech": raw_transcript
                }

            content = llm_res.json()['choices'][0]['message']['content']
            return json.loads(content)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================= Dynamic Metrics CRUD APIs =================

@app.get("/api/metrics")
async def get_metrics(user: dict = Depends(verify_firebase_token)):
    global cached_metrics_data, cache_metrics_timestamp
    
    now = datetime.now()
    if cached_metrics_data and cache_metrics_timestamp and (now - cache_metrics_timestamp).total_seconds() < METRICS_CACHE_TTL_SECONDS:
        return cached_metrics_data

    if not db:
        return DEFAULT_METRICS
    try:
        loop = asyncio.get_running_loop()
        def fetch_metrics_db():
            docs = db.collection("metrics").stream()
            metrics = []
            for doc in docs:
                m = doc.to_dict()
                m["id"] = doc.id
                metrics.append(m)
            return metrics
        
        result = await loop.run_in_executor(None, fetch_metrics_db)
        cached_metrics_data = result
        cache_metrics_timestamp = now
        return result
    except Exception as e:
        print("❌ Firebase Fetch Metrics Error:", str(e))
        return cached_metrics_data if cached_metrics_data else DEFAULT_METRICS

@app.post("/api/metrics")
async def create_metric(
    payload: Dict[str, str] = Body(...), 
    user: dict = Depends(verify_firebase_token)
):
    if not db:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    key = payload.get("key", "").strip()
    label = payload.get("label", "").strip()
    description = payload.get("description", "").strip()

    if not key or not label or not description:
        raise HTTPException(status_code=400, detail="All fields are required.")

    loop = asyncio.get_running_loop()
    def save_to_db():
        existing = db.collection("metrics").where("key", "==", key).get()
        if len(existing) > 0:
            raise HTTPException(status_code=400, detail=f"Metric key '{key}' already exists.")

        doc_ref = db.collection("metrics").add({
            "key": key,
            "label": label,
            "description": description
        })
        return doc_ref[1].id

    doc_id = await loop.run_in_executor(None, save_to_db)
    invalidate_metrics_cache()
    return {"status": "success", "id": doc_id}

@app.put("/api/metrics/{metric_id}")
async def update_metric(
    metric_id: str, 
    payload: Dict[str, str] = Body(...),
    user: dict = Depends(verify_firebase_token)
):
    if not db:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    label = payload.get("label", "").strip()
    description = payload.get("description", "").strip()

    if not label or not description:
        raise HTTPException(status_code=400, detail="Fields label & description are required.")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: db.collection("metrics").document(metric_id).update({
        "label": label,
        "description": description
    }))
    invalidate_metrics_cache()
    return {"status": "success"}

@app.delete("/api/metrics/{metric_id}")
async def delete_metric(
    metric_id: str,
    user: dict = Depends(verify_firebase_token)
):
    if not db:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: db.collection("metrics").document(metric_id).delete())
    invalidate_metrics_cache()
    return {"status": "success"}

# ================= Core Transcription Logic =================

async def transcribe_bytes_async(audio_bytes: bytes):
    url = "https://api.deepgram.com/v1/listen?model=nova-2&language=hi&detect_language=true&diarize=true&punctuate=true&utterances=true"
    headers = {"Authorization": "Token " + DEEPGRAM_API_KEY, "Content-Type": "audio/mp3"}
    
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(url, headers=headers, content=audio_bytes)
        if response.status_code != 200:
            raise Exception(f"Deepgram Error ({response.status_code}): {response.text}")
            
        data = response.json()
        duration = float(data.get("metadata", {}).get("duration", 0.0))
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

async def evaluate_quality_async(transcript, metrics_list):
    evaluated_metrics_json = {}
    metric_instructions = []

    for m in metrics_list:
        m_key = m.get("key")
        m_desc = m.get("description", "")
        evaluated_metrics_json[m_key] = True
        metric_instructions.append(f'- "{m_key}": {m_desc} (boolean)')

    metrics_guide = "\n".join(metric_instructions)
    compact_transcript_text = "\n".join([f"{item['speaker']}: {item['text']}" for item in transcript])

    prompt = f"""
    Analyze the following audio call transcript and evaluate quality score (0-100) and evaluated metrics.
    
    Evaluation Rules for Metrics:
    {metrics_guide}

    Scoring Rule:
    - Base score is 100.
    - Deduct fixed points consistently for any agent mistakes or missing compliance.
    - Be completely objective and deterministic in scoring.

    Transcript:
    {compact_transcript_text}

    Return JSON strictly matching this schema format ONLY:
    {{
        "overall_score": 85,
        "summary": "Detailed call summary...",
        "evaluated_metrics": {json.dumps(evaluated_metrics_json)},
        "strengths": ["Strong point 1", "Strong point 2"],
        "improvements": ["Improvement point 1", "Improvement point 2"]
    }}
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.0
        }
    }

    max_retries = 10
    retry_delay = 2.5

    async with httpx.AsyncClient(timeout=360.0) as client:
        for attempt in range(max_retries):
            active_key = get_next_gemini_key()
            if not active_key:
                raise Exception("No GEMINI_KEYS found in environment variables.")

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={active_key}"
            headers = {"Content-Type": "application/json"}

            try:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    res_data = response.json()
                    raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
                    clean_json = re.sub(r'```(?:json)?\n?', '', raw_text).replace('```', '').strip()
                    return json.loads(clean_json)
                elif response.status_code in [429, 500, 503]:
                    await asyncio.sleep(retry_delay)
                    retry_delay += 2.0
                elif response.status_code == 403:
                    await asyncio.sleep(1.0)
                else:
                    raise Exception(f"Gemini Error ({response.status_code}): {response.text}")
            except (httpx.TimeoutException, httpx.RequestError):
                await asyncio.sleep(retry_delay)
                retry_delay += 2.0

    raise Exception("Gemini Rate Limit Exceeded after retries.")

async def process_single_file(file: UploadFile, active_metrics: List[Dict], user_info: dict = None):
    try:
        audio_bytes = await file.read()
        transcript, metrics = await transcribe_bytes_async(audio_bytes)
        evaluation = await evaluate_quality_async(transcript, active_metrics)
        
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        created_time = datetime.now(ist_tz).isoformat()

        uploader_name = "Admin"
        if user_info and isinstance(user_info, dict):
            email = user_info.get("email", "")
            name = user_info.get("name", "")
            if name:
                uploader_name = name
            elif email:
                uploader_name = email.split("@")[0]

        calc_duration = round(float(metrics.get("duration", 0.0)), 2)
        calc_total_words = int(metrics.get("total_words", 0))
        calc_wpm = int(metrics.get("wpm", 0))

        if db:
            try:
                audit_data = {
                    "filename": file.filename,
                    "uploaded_by": uploader_name,
                    "score": evaluation.get("overall_score", 0),
                    "summary": evaluation.get("summary", ""),
                    "evaluated_metrics": evaluation.get("evaluated_metrics", {}),
                    "strengths": evaluation.get("strengths", []),
                    "improvements": evaluation.get("improvements", []),
                    "wpm": calc_wpm,
                    "duration": calc_duration,
                    "total_words": calc_total_words,
                    "transcript": transcript,
                    "created_at": created_time
                }
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, lambda: db.collection("audits").add(audit_data))
                invalidate_history_cache()
            except Exception as fe:
                print("❌ Firebase Write Error:", fe)

        return {
            "status": "success", 
            "filename": file.filename, 
            "data": {
                "metrics": {
                    "duration": calc_duration,
                    "total_words": calc_total_words,
                    "wpm": calc_wpm
                }, 
                "transcript": transcript, 
                "evaluation": evaluation
            }
        }
    except Exception as e:
        return {"status": "error", "filename": file.filename, "error": str(e)}

async def process_single_file_limited(file: UploadFile, active_metrics: List[Dict], user_info: dict = None):
    async with semaphore:
        return await process_single_file(file, active_metrics, user_info)

# ================= Batch Analysis & History APIs =================

@app.post("/api/analyze-batch")
async def analyze_audio_batch(
    files: List[UploadFile] = File(...),
    user: dict = Depends(verify_firebase_token)
):
    if db:
        loop = asyncio.get_running_loop()
        def fetch_metrics_db():
            docs = db.collection("metrics").stream()
            return [doc.to_dict() for doc in docs]
        active_metrics = await loop.run_in_executor(None, fetch_metrics_db)
    else:
        active_metrics = DEFAULT_METRICS

    tasks = [process_single_file_limited(file, active_metrics, user) for file in files]
    results = await asyncio.gather(*tasks)
    invalidate_history_cache()
    return {"results": results}

@app.get("/api/history")
async def get_history(limit: Optional[int] = 50, refresh: Optional[bool] = False, user: dict = Depends(verify_firebase_token)):
    global cached_history_data, cache_history_timestamp

    now = datetime.now()
    if not refresh and limit != 0 and cached_history_data and cache_history_timestamp and (now - cache_history_timestamp).total_seconds() < HISTORY_CACHE_TTL_SECONDS:
        return cached_history_data[:limit] if limit else cached_history_data

    if not db:
        return []
    try:
        loop = asyncio.get_running_loop()
        def fetch_db():
            query = db.collection("audits").order_by("created_at", direction=firestore.Query.DESCENDING)
            
            if limit and limit > 0:
                query = query.limit(limit)
                
            docs = query.stream()
            history = []
            for doc in docs:
                data = doc.to_dict()
                if data:
                    data["id"] = doc.id
                    history.append(data)
            return history

        result = await loop.run_in_executor(None, fetch_db)
        
        if limit == 50:
            cached_history_data = result
            cache_history_timestamp = now
            
        return result
    except Exception as e:
        print("❌ Firebase Fetch Error:", str(e))
        return cached_history_data if cached_history_data else []

@app.delete("/api/history/delete-all")
async def delete_all_history_data(user: dict = Depends(verify_firebase_token)):
    if not db:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        loop = asyncio.get_running_loop()
        def wipe_collection():
            docs = db.collection("audits").stream()
            count = 0
            for doc in docs:
                doc.reference.delete()
                count += 1
            return count

        deleted_count = await loop.run_in_executor(None, wipe_collection)
        invalidate_history_cache()
        return {"status": "success", "message": "All audits deleted successfully", "deleted_count": deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/history/{audit_id}")
async def delete_audit_history(
    audit_id: str,
    user: dict = Depends(verify_firebase_token)
):
    if not db:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: db.collection("audits").document(audit_id).delete())
        invalidate_history_cache()
        return {"status": "success", "message": "Audit record deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
