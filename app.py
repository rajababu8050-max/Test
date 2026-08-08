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

# ================= HTML Content (Main Dashboard) =================

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Call Quality Auditor Pro (Bulk 50+ Audio)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = { darkMode: 'class' }
    </script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
    <script src="https://www.gstatic.com/firebasejs/9.22.1/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/9.22.1/firebase-auth-compat.js"></script>

    <style>
        .dark body { background-color: #0f172a; color: #f8fafc; }
        body { background-color: #f8fafc; color: #0f172a; transition: background-color 0.3s, color 0.3s; }
        .card-bg { background-color: #1e293b; }
        .light .card-bg { background-color: #ffffff; border-color: #e2e8f0; color: #1e293b; }
        .inner-bg { background-color: #0f172a; }
        .light .inner-bg { background-color: #f1f5f9; color: #1e293b; }
        .text-sub { color: #94a3b8; }
        .light .text-sub { color: #64748b; }
    </style>
</head>
<body class="min-h-screen p-4 md:p-8 font-sans">

    <!-- ADMIN LOGIN MODAL -->
    <div id="authModal" class="fixed inset-0 bg-slate-950/90 backdrop-blur-md flex items-center justify-center p-4 z-[100]">
        <div class="card-bg border border-slate-700 rounded-2xl w-full max-w-md p-6 space-y-6 shadow-2xl">
            <div class="text-center space-y-2">
                <div class="w-12 h-12 bg-blue-500/10 text-blue-400 rounded-full flex items-center justify-center mx-auto text-xl font-bold">🔒</div>
                <h2 class="text-2xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">
                    Admin Portal Access
                </h2>
                <p class="text-xs text-sub">Please sign in with your Firebase credentials</p>
            </div>
            <form onsubmit="handleLogin(event)" class="space-y-4">
                <div>
                    <label class="block text-xs font-semibold text-sub mb-1">Admin Email</label>
                    <input type="email" id="adminEmail" required placeholder="admin@example.com" class="w-full card-bg border border-slate-600 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-blue-500">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-sub mb-1">Password</label>
                    <input type="password" id="adminPassword" required placeholder="••••••••" class="w-full card-bg border border-slate-600 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-blue-500">
                </div>
                <div id="authError" class="text-rose-400 text-xs text-center hidden font-medium"></div>
                <button type="submit" id="loginBtn" class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-2.5 rounded-xl text-xs transition shadow-lg shadow-blue-500/20">
                    Sign In
                </button>
            </form>
        </div>
    </div>

    <!-- MAIN PROTECTED DASHBOARD CONTENT -->
    <div id="dashboardContent" class="hidden max-w-6xl mx-auto space-y-6">
        <div class="flex justify-between items-center border-b border-slate-700/60 pb-4 flex-wrap gap-3">
            <div>
                <h1 class="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">
                    AI Call Quality Auditor Pro
                </h1>
                <p class="text-sub text-sm">Pharma Metrics Evaluation & Bulk Batch Quality Auditing</p>
            </div>
            <div class="flex items-center gap-3 flex-wrap">
                <a href="/ai.html" class="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white font-bold px-4 py-2 rounded-xl text-xs sm:text-sm shadow-lg shadow-purple-500/30 flex items-center gap-2 transform hover:-translate-y-0.5 transition duration-200 border border-purple-400/30">
                    ✨ AI Quality Score
                </a>
                <button onclick="toggleTheme()" class="card-bg border border-slate-600 px-3 py-2 rounded-xl text-xs font-bold flex items-center gap-2 shadow">
                    <span id="themeIcon">🌙</span> <span id="themeText">Dark Mode</span>
                </button>
                <button onclick="openMetricModal()" class="bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-4 py-2 rounded-xl text-sm shadow-lg shadow-indigo-500/20 flex items-center gap-2">
                    ⚙️ Manage Metrics
                </button>
                
                <!-- USER PROFILE BADGE & LOGOUT -->
                <div class="flex items-center gap-2 bg-slate-800/80 border border-slate-700 px-3 py-1.5 rounded-xl">
                    <span class="text-xs text-emerald-400 font-bold flex items-center gap-1">
                        👤 <span id="userDisplayName">Loading...</span>
                    </span>
                    <button onclick="handleLogout()" class="bg-rose-600 hover:bg-rose-500 text-white font-bold px-2.5 py-1 rounded-lg text-xs shadow-md shadow-rose-600/20 transition ml-1">
                        🚪 Logout
                    </button>
                </div>
            </div>
        </div>

        <div class="card-bg border-2 border-dashed border-slate-600 rounded-2xl p-6 text-center shadow-lg">
            <div class="space-y-3">
                <div class="w-12 h-12 bg-blue-500/10 text-blue-400 rounded-full flex items-center justify-center mx-auto text-xl font-bold">🎙️</div>
                <p id="fileName" class="text-sm font-medium">Select Audio File(s) (.mp3, .wav, .m4a)</p>
                <input type="file" id="audioInput" accept="audio/*" multiple class="hidden" onchange="fileSelected(event)">
                <div class="flex justify-center gap-3">
                    <button type="button" onclick="document.getElementById('audioInput').click()" class="inner-bg border border-slate-600 font-medium px-4 py-2 rounded-xl text-sm">Browse Files</button>
                    <button type="button" onclick="uploadAudioBatch()" class="bg-blue-600 hover:bg-blue-500 text-white font-medium px-5 py-2 rounded-xl text-sm shadow-lg shadow-blue-500/20">🚀 Start Bulk Batch Analysis</button>
                </div>
            </div>
            <div id="progressContainer" class="hidden mt-4 space-y-2">
                <div class="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
                    <div id="progressBar" class="bg-gradient-to-r from-blue-500 to-emerald-400 h-2.5 rounded-full transition-all duration-300" style="width: 0%"></div>
                </div>
                <div id="loaderText" class="text-xs text-blue-400 font-medium">⚡ Auditing... 0 / 0 Completed</div>
            </div>
        </div>

        <div id="batchResultsContainer" class="hidden space-y-6">
            <div class="flex justify-between items-center font-semibold border-b border-slate-700/60 pb-2 flex-wrap gap-2">
                <span class="text-lg text-emerald-400 font-bold">📊 Batch Analysis Summary Report</span>
                <div class="flex gap-2">
                    <button type="button" onclick="downloadExcel()" class="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-4 py-2 rounded-xl flex items-center gap-1 shadow-lg shadow-emerald-600/20">📊 Export Detailed Excel (.xlsx)</button>
                    <button type="button" onclick="downloadPDF()" class="bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold px-4 py-2 rounded-xl flex items-center gap-1">📥 Export PDF Report</button>
                </div>
            </div>
            <div id="summaryTableContainer" class="card-bg border border-slate-700 rounded-2xl p-5 shadow-xl space-y-4">
                <div class="flex justify-between items-center border-b border-slate-700 pb-3">
                    <div>
                        <h3 class="text-base font-bold text-blue-400">💊 Aggregate Metrics Summary</h3>
                        <p class="text-xs text-sub" id="summaryTimeSlot">Batch Analytics</p>
                    </div>
                    <span id="totalCallsBadge" class="bg-blue-500/20 text-blue-400 text-xs font-bold px-3 py-1 rounded-full border border-blue-500/30">Total Calls: 0</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm border-collapse">
                        <thead>
                            <tr class="inner-bg uppercase text-xs border-b border-slate-700">
                                <th class="p-3">Metric</th>
                                <th class="p-3 text-center">Count</th>
                                <th class="p-3 text-center">%</th>
                            </tr>
                        </thead>
                        <tbody id="summaryTableBody" class="divide-y divide-slate-700/50 text-xs md:text-sm"></tbody>
                    </table>
                </div>
            </div>
            <h3 class="text-md font-bold pt-2 border-b border-slate-700/60 pb-2">📁 Individual Call Breakdowns</h3>
            <div id="resultsList" class="space-y-4"></div>
        </div>

        <!-- FIREBASE CLOUD HISTORY TABLE WITH GLOBAL ACTIONS & METRIC FILTER -->
        <div class="card-bg border border-slate-700 rounded-2xl p-6 space-y-4 shadow-lg">
            <div class="flex justify-between items-center border-b border-slate-700 pb-3 flex-wrap gap-2">
                <div class="flex items-center gap-2 flex-wrap">
                    <h3 class="text-sm font-semibold">🔥 Firebase Cloud Audits History</h3>
                    <span id="totalHistoryBadge" class="bg-blue-500/20 text-blue-400 text-xs font-bold px-2 py-0.5 rounded-full border border-blue-500/30">0 Total Records</span>
                </div>
                <!-- GLOBAL ACTIONS CONTROL -->
                <div class="flex gap-2 flex-wrap items-center">
                    <button type="button" onclick="exportHistoryExcel()" class="text-xs bg-emerald-700 hover:bg-emerald-600 px-3 py-1.5 rounded-lg text-white font-medium flex items-center gap-1 shadow-lg shadow-emerald-700/20">
                        📊 Export ALL Data to Excel
                    </button>
                    <button type="button" onclick="deleteAllHistoryData()" class="text-xs bg-rose-700 hover:bg-rose-600 px-3 py-1.5 rounded-lg text-white font-bold flex items-center gap-1 shadow-lg shadow-rose-700/20">
                        🔥 Delete ALL Data
                    </button>
                    <button type="button" onclick="loadHistory()" class="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded-lg text-slate-300">
                        Refresh
                    </button>
                </div>
            </div>

            <!-- METRIC FILTER CONTROL BAR -->
            <div class="inner-bg p-3 rounded-xl border border-slate-700/60 flex items-center gap-3 flex-wrap text-xs">
                <span class="font-bold text-blue-400 flex items-center gap-1">🔍 Filter By Metric:</span>
                
                <select id="metricFilterSelect" onchange="applyMetricFilter()" class="card-bg border border-slate-600 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500 max-w-xs">
                    <option value="ALL">-- Select Metric --</option>
                </select>

                <select id="metricFilterValue" onchange="applyMetricFilter()" class="card-bg border border-slate-600 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500">
                    <option value="ALL">Status: ALL</option>
                    <option value="YES">YES ✅</option>
                    <option value="NO">NO ❌</option>
                </select>

                <button onclick="resetMetricFilter()" class="bg-slate-700 hover:bg-slate-600 text-slate-300 px-3 py-1.5 rounded-lg transition font-medium">
                    Reset Filter
                </button>

                <!-- EXPORT FILTERED EXCEL BUTTON -->
                <button type="button" onclick="exportFilteredExcel()" class="bg-teal-700 hover:bg-teal-600 text-white font-semibold px-3 py-1.5 rounded-lg transition flex items-center gap-1 shadow-lg shadow-teal-700/20">
                    📥 Export Filtered Data to Excel
                </button>

                <span id="filterCountBadge" class="text-sub font-medium ml-auto"></span>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs text-sub">
                    <thead class="inner-bg uppercase font-semibold">
                        <tr>
                            <th class="p-2">File</th>
                            <th class="p-2">Uploaded By</th>
                            <th class="p-2">Score</th>
                            <th class="p-2">Summary</th>
                            <th class="p-2">Date & Time (IST)</th>
                            <th class="p-2 text-center">Action</th>
                        </tr>
                    </thead>
                    <tbody id="historyTable">
                        <tr><td colspan="6" class="p-3 text-center text-slate-500">Loading full history...</td></tr>
                    </tbody>
                </table>
            </div>

            <div class="flex justify-between items-center pt-2 text-xs border-t border-slate-700/60">
                <span id="pageInfoText" class="text-sub font-medium">Page 1 of 1</span>
                <div class="flex gap-2">
                    <button id="prevPageBtn" onclick="changePage(-1)" disabled class="inner-bg border border-slate-600 px-3 py-1 rounded-lg text-sub hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition">← Prev</button>
                    <button id="nextPageBtn" onclick="changePage(1)" disabled class="inner-bg border border-slate-600 px-3 py-1 rounded-lg text-sub hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition">Next →</button>
                </div>
            </div>
        </div>
    </div>

    <!-- METRICS MODAL -->
    <div id="metricsModal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm hidden items-center justify-center p-4 z-50">
        <div class="card-bg border border-slate-700 rounded-2xl w-full max-w-2xl p-6 space-y-6 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div class="flex justify-between items-center border-b border-slate-700 pb-3">
                <h3 class="text-lg font-bold">⚙️ Configure Dynamic Metrics</h3>
                <button onclick="closeMetricModal()" class="text-sub hover:text-white font-bold text-lg">&times;</button>
            </div>
            <form id="metricForm" onsubmit="saveMetric(event)" class="inner-bg p-4 rounded-xl border border-slate-700 space-y-3">
                <input type="hidden" id="metricId" value="">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-semibold text-sub mb-1">Metric Key (Unique slug)</label>
                        <input type="text" id="metricKey" required placeholder="e.g. discount_offered" class="w-full card-bg border border-slate-600 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-blue-500">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-sub mb-1">Display Label</label>
                        <input type="text" id="metricLabel" required placeholder="e.g. Discount Offered" class="w-full card-bg border border-slate-600 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-blue-500">
                    </div>
                </div>
                <div>
                    <label class="block text-xs font-semibold text-sub mb-1">Description (Guides AI Evaluation)</label>
                    <input type="text" id="metricDesc" required placeholder="e.g. Did agent offer any promotional discount?" class="w-full card-bg border border-slate-600 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-blue-500">
                </div>
                <div class="flex justify-end gap-2 pt-2">
                    <button type="button" onclick="resetMetricForm()" class="bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs px-3 py-1.5 rounded-lg">Clear</button>
                    <button type="submit" class="bg-blue-600 hover:bg-blue-500 text-white text-xs px-4 py-1.5 rounded-lg font-bold">Save Metric</button>
                </div>
            </form>
            <div class="space-y-3">
                <h4 class="text-xs font-bold text-sub uppercase tracking-wider">Active Evaluated Metrics</h4>
                <div id="metricsListContainer" class="space-y-2"></div>
            </div>
        </div>
    </div>

    <script>
        const firebaseConfig = {
          apiKey: "AIzaSyDQfBUENJ87idiFkHUCGXWjjt8o8ZpxX1M",
          authDomain: "ai-call-quality-auditor-pro.firebaseapp.com",
          databaseURL: "https://ai-call-quality-auditor-pro-default-rtdb.firebaseio.com",
          projectId: "ai-call-quality-auditor-pro",
          storageBucket: "ai-call-quality-auditor-pro.firebasestorage.app",
          messagingSenderId: "788716678382",
          appId: "1:788716678382:web:778853207b4fa11e0517ff",
          measurementId: "G-R4R06JN2SK"
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

        auth.onAuthStateChanged(async (user) => {
            if (user) {
                idToken = await user.getIdToken(true);
                
                currentUserName = user.displayName || (user.email ? user.email.split('@')[0] : "Admin");
                document.getElementById('userDisplayName').innerText = currentUserName;

                document.getElementById('authModal').classList.add('hidden');
                document.getElementById('dashboardContent').classList.remove('hidden');
                await fetchMetrics();
                loadHistory();
            } else {
                idToken = "";
                document.getElementById('authModal').classList.remove('hidden');
                document.getElementById('dashboardContent').classList.add('hidden');
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
                loginBtn.innerText = "Signing in...";
                await auth.signInWithEmailAndPassword(email, password);
            } catch (error) {
                errorDiv.innerText = error.message;
                errorDiv.classList.remove('hidden');
            } finally {
                loginBtn.innerText = "Sign In";
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

        function toggleTheme() {
            var html = document.documentElement;
            if(html.classList.contains('dark')) {
                html.classList.remove('dark');
                html.classList.add('light');
                document.getElementById('themeIcon').innerText = "☀️";
                document.getElementById('themeText').innerText = "Light Mode";
            } else {
                html.classList.remove('light');
                html.classList.add('dark');
                document.getElementById('themeIcon').innerText = "🌙";
                document.getElementById('themeText').innerText = "Dark Mode";
            }
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
                <div class="inner-bg p-3 rounded-xl border border-slate-700/60 flex justify-between items-center text-xs">
                    <div>
                        <span class="font-bold text-blue-400">${m.label}</span>
                        <span class="text-sub text-[10px] ml-2">(${m.key})</span>
                        <p class="text-sub text-[11px] mt-0.5">${m.description}</p>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="editMetric('${m.id}')" class="text-blue-400 hover:text-blue-300 bg-blue-500/10 px-2 py-1 rounded">Edit</button>
                        <button onclick="deleteMetric('${m.id}')" class="text-rose-400 hover:text-rose-300 bg-rose-500/10 px-2 py-1 rounded">Delete</button>
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
                document.getElementById('fileName').innerText = selectedFiles.length + " file(s) selected";
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
            setTimeout(loadHistory, 1000);
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

            var summaryHtml = `<tr class="hover:bg-slate-700/20"><td class="p-2.5 font-medium">Total Calls Reviewed</td><td class="p-2.5 text-center font-bold text-blue-400">${totalCalls}</td><td class="p-2.5 text-center font-extrabold text-emerald-400">100%</td></tr>`;
            activeMetrics.forEach(m => {
                var cnt = metricCounts[m.key] || 0;
                summaryHtml += `<tr class="hover:bg-slate-700/20"><td class="p-2.5 font-medium">${m.label}</td><td class="p-2.5 text-center font-bold text-blue-400">${cnt}</td><td class="p-2.5 text-center font-extrabold text-emerald-400">${calcPct(cnt)}</td></tr>`;
            });
            document.getElementById('summaryTableBody').innerHTML = summaryHtml;

            results.forEach(item => {
                if(item.status !== "success") {
                    container.innerHTML += `<div class="bg-red-900/30 border border-red-700 p-4 rounded-xl text-red-300 text-xs">❌ Failed: ${item.filename}</div>`;
                    return;
                }
                var data = item.data || {};
                var evalData = data.evaluation || {};
                var evalMetrics = evalData.evaluated_metrics || {};
                var metrics = data.metrics || {};
                var transcript = data.transcript || [];
                
                var card = document.createElement('div');
                card.className = "card-bg border border-slate-700 rounded-2xl p-5 shadow-lg space-y-4";
                
                var transcriptHtml = "";
                transcript.forEach(t => {
                    var colorClass = t.speaker === 'Agent' ? 'text-blue-400' : 'text-emerald-400';
                    transcriptHtml += `<div class="mb-1"><b class="${colorClass}">${t.speaker}:</b> ${t.text}</div>`;
                });

                var dynamicCardsHtml = '';
                activeMetrics.forEach(m => {
                    var fmt = evalMetrics[m.key] ? '<span class="text-emerald-400 font-bold">YES</span>' : '<span class="text-rose-400 font-bold">NO</span>';
                    dynamicCardsHtml += `<div class="inner-bg p-2 rounded border border-slate-700/40">${m.label}:${fmt}</div>`;
                });

                card.innerHTML = `
                    <div class="flex justify-between items-center border-b border-slate-700 pb-3">
                        <h3 class="font-bold text-blue-400 text-sm">📁 ${item.filename}</h3>
                        <span class="text-emerald-400 font-extrabold text-lg">${evalData.overall_score || 0}/100</span>
                    </div>
                    <div class="grid grid-cols-3 gap-2 text-center text-xs">
                        <div class="inner-bg p-2 rounded-lg"><span class="text-sub block text-[10px]">PACE</span><span class="font-bold text-blue-400">${metrics.wpm || 0} WPM</span></div>
                        <div class="inner-bg p-2 rounded-lg"><span class="text-sub block text-[10px]">DURATION</span><span class="font-bold text-indigo-400">${Math.round(metrics.duration || 0)}s</span></div>
                        <div class="inner-bg p-2 rounded-lg"><span class="text-sub block text-[10px]">WORDS</span><span class="font-bold text-amber-400">${metrics.total_words || 0}</span></div>
                    </div>
                    <div class="inner-bg p-3 rounded-xl border border-slate-700/60 space-y-2">
                        <div class="font-bold text-emerald-400 text-[11px] uppercase">💊 Call Metrics Evaluation</div>
                        <div class="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">${dynamicCardsHtml}</div>
                    </div>
                    <div class="text-xs inner-bg p-3 rounded-xl border border-slate-700/50 space-y-1">
                        <div class="font-bold text-blue-300 text-[11px] uppercase">Detailed Call Summary</div>
                        <p class="text-sub leading-relaxed">${evalData.summary || "N/A"}</p>
                    </div>
                    <details class="inner-bg p-3 rounded-xl border border-slate-700/50 text-xs">
                        <summary class="font-bold text-sub cursor-pointer">📄 Full Diarized Transcript</summary>
                        <div class="mt-3 space-y-2 max-h-48 overflow-y-auto pr-2 pt-2 border-t border-slate-800">${transcriptHtml}</div>
                    </details>`;
                container.appendChild(card);
            });
        }

        async function loadHistory() {
            var hTable = document.getElementById('historyTable');
            try {
                if (!auth.currentUser) return;
                idToken = await auth.currentUser.getIdToken(true);
                var res = await fetchAuth("/api/history");
                if(!res.ok) throw new Error("HTTP error " + res.status);
                var list = await res.json();
                historyDataList = list || [];
                document.getElementById('totalHistoryBadge').innerText = historyDataList.length + " Total Records";
                
                applyMetricFilter();
            } catch(e) {
                hTable.innerHTML = '<tr><td colspan="6" class="p-3 text-center text-rose-500">Failed to load history.</td></tr>';
            }
        }

        // ================= METRIC FILTER LOGIC =================

        function applyMetricFilter() {
            var selectedMetricKey = document.getElementById('metricFilterSelect').value;
            var selectedValue = document.getElementById('metricFilterValue').value;

            if (selectedMetricKey === "ALL") {
                filteredHistoryList = [...historyDataList];
                document.getElementById('filterCountBadge').innerText = "";
            } else {
                filteredHistoryList = historyDataList.filter(item => {
                    var evalMetrics = item.evaluated_metrics || {};
                    var metricVal = evalMetrics[selectedMetricKey];

                    if (selectedValue === "YES") {
                        return metricVal === true;
                    } else if (selectedValue === "NO") {
                        return metricVal === false || metricVal === undefined;
                    } else {
                        return true; // Status ALL chosen
                    }
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
                hTable.innerHTML = '<tr><td colspan="6" class="p-3 text-center text-slate-500">No audits found for selected filter.</td></tr>';
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
                
                // Fallback Logic for Uploader Name
                var uploadedUser = item.uploaded_by;
                if (!uploadedUser || uploadedUser === "Unknown") {
                    uploadedUser = currentUserName || "Admin";
                }
                
                hTable.innerHTML += `
                    <tr class="border-b border-slate-700/50 hover:bg-slate-700/20">
                        <td class="p-2 font-medium">${item.filename || 'N/A'}</td>
                        <td class="p-2 font-semibold text-indigo-300">👤 ${uploadedUser}</td>
                        <td class="p-2 text-emerald-400 font-bold">${item.score || 0}/100</td>
                        <td class="p-2 text-sub max-w-xs truncate">${item.summary || 'N/A'}</td>
                        <td class="p-2 text-sub">${formatDateDisplay(item.created_at)}</td>
                        <td class="p-2 text-center">
                            <div class="flex items-center justify-center gap-1.5">
                                <button onclick="viewHistoryDetails(${globalIndex})" title="View Details" class="bg-blue-600/20 text-blue-400 hover:bg-blue-600 hover:text-white px-2 py-1 rounded text-[11px] font-medium transition">
                                    👁️ View
                                </button>
                                <button onclick="downloadSingleHistoryExcel(${globalIndex})" title="Export Excel" class="bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600 hover:text-white px-2 py-1 rounded text-[11px] font-medium transition">
                                    📊 Excel
                                </button>
                                <button onclick="deleteHistoryItem('${item.id}', ${globalIndex})" title="Delete Audit" class="bg-rose-600/20 text-rose-400 hover:bg-rose-600 hover:text-white px-2 py-1 rounded text-[11px] font-medium transition">
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

        // Export Filtered Items to Excel
        function exportFilteredExcel() {
            var targetItems = filteredHistoryList || [];
            if(targetItems.length === 0) {
                return alert("Export karne ke liye koi filtered data nahi mila!");
            }

            var exportData = targetItems.map(item => {
                var row = {
                    "File Name": item.filename || "N/A",
                    "Uploaded By": item.uploaded_by || currentUserName || "Admin",
                    "QA Score": item.score || 0,
                    "WPM": item.wpm || 0,
                    "Duration (sec)": Math.round(item.duration || 0),
                    "Total Words": item.total_words || 0,
                    "Date & Time (IST)": formatDateDisplay(item.created_at),
                    "Summary": item.summary || ""
                };
                var evalMetrics = item.evaluated_metrics || {};
                activeMetrics.forEach(m => row[m.label] = (evalMetrics[m.key] === true) ? "YES" : "NO");
                return row;
            });

            var workbook = XLSX.utils.book_new();
            var sheet = XLSX.utils.json_to_sheet(exportData);
            XLSX.utils.book_append_sheet(workbook, sheet, "Filtered Audits");
            XLSX.writeFile(workbook, `Filtered_Audits_Export_${targetItems.length}.xlsx`);
        }

        // Export ALL History Data to Excel
        function exportHistoryExcel() {
            if(!historyDataList || historyDataList.length === 0) return alert("History empty!");
            var exportData = historyDataList.map(item => {
                var row = {
                    "File Name": item.filename || "N/A",
                    "Uploaded By": item.uploaded_by || currentUserName || "Admin",
                    "QA Score": item.score || 0,
                    "WPM": item.wpm || 0,
                    "Duration (sec)": Math.round(item.duration || 0),
                    "Total Words": item.total_words || 0,
                    "Date & Time (IST)": formatDateDisplay(item.created_at),
                    "Summary": item.summary || ""
                };
                var evalMetrics = item.evaluated_metrics || {};
                activeMetrics.forEach(m => row[m.label] = (evalMetrics[m.key] === true) ? "YES" : "NO");
                return row;
            });

            var workbook = XLSX.utils.book_new();
            var sheet = XLSX.utils.json_to_sheet(exportData);
            XLSX.utils.book_append_sheet(workbook, sheet, "All Cloud Audit History");
            XLSX.writeFile(workbook, `Complete_Cloud_Audit_History_${historyDataList.length}.xlsx`);
        }

        // DELETE ALL DATA IN FIRESTORE
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
                await loadHistory();
            } catch(err) {
                alert("Error deleting all data: " + err.message);
            }
        }

        function viewHistoryDetails(index) {
            var item = filteredHistoryList[index];
            if(!item) return;

            var metricsInfo = "";
            var evalMetrics = item.evaluated_metrics || {};
            
            activeMetrics.forEach(m => {
                var statusStr = evalMetrics[m.key] ? "YES ✅" : "NO ❌";
                metricsInfo += `\n• ${m.label}: ${statusStr}`;
            });

            var uName = item.uploaded_by || currentUserName || 'Admin';
            var detailText = `📁 File: ${item.filename}\n👤 Uploaded By: ${uName}\n⭐ Quality Score: ${item.score}/100\n⏱️ Duration: ${Math.round(item.duration || 0)}s | WPM: ${item.wpm || 0}\n\n📝 Summary:\n${item.summary}\n\n💊 Evaluated Metrics:${metricsInfo}`;
            alert(detailText);
        }

        function downloadSingleHistoryExcel(index) {
            var item = filteredHistoryList[index];
            if(!item) return;

            var row = {
                "File Name": item.filename || "N/A",
                "Uploaded By": item.uploaded_by || currentUserName || "Admin",
                "QA Score": item.score || 0,
                "WPM": item.wpm || 0,
                "Duration (sec)": Math.round(item.duration || 0),
                "Total Words": item.total_words || 0,
                "Date & Time (IST)": formatDateDisplay(item.created_at),
                "Summary": item.summary || ""
            };
            
            var evalMetrics = item.evaluated_metrics || {};
            activeMetrics.forEach(m => {
                row[m.label] = (evalMetrics[m.key] === true) ? "YES" : "NO";
            });

            var workbook = XLSX.utils.book_new();
            var sheet = XLSX.utils.json_to_sheet([row]);
            XLSX.utils.book_append_sheet(workbook, sheet, "Audit Details");
            XLSX.writeFile(workbook, `${item.filename}_Audit.xlsx`);
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

                await loadHistory();
                alert("Record deleted successfully!");
            } catch(err) {
                alert("Error deleting record: " + err.message);
            }
        }

        function downloadExcel() {
            if(!currentBatchResults || currentBatchResults.length === 0) return alert("No data!");
            var exportData = currentBatchResults.map(i => {
                var row = {
                    "File Name": i.filename,
                    "QA Score": i.data?.evaluation?.overall_score || 0,
                    "WPM": i.data?.metrics?.wpm || 0,
                    "Duration (sec)": Math.round(i.data?.metrics?.duration || 0),
                    "Total Words": i.data?.metrics?.total_words || 0,
                    "Summary": i.data?.evaluation?.summary || ""
                };
                var evalMetrics = i.data?.evaluation?.evaluated_metrics || {};
                activeMetrics.forEach(m => row[m.label] = (evalMetrics[m.key] === true) ? "YES" : "NO");
                return row;
            });
            var workbook = XLSX.utils.book_new();
            var summarySheet = XLSX.utils.json_to_sheet(exportData);
            XLSX.utils.book_append_sheet(workbook, summarySheet, "Batch Summary");
            XLSX.writeFile(workbook, "Detailed_Call_Audit_Report.xlsx");
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

# ================= Groq ONLY Audio Transcribe & Diarize API =================

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

# ================= Dynamic Metrics CRUD APIs (Protected) =================

@app.get("/api/metrics")
async def get_metrics(user: dict = Depends(verify_firebase_token)):
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
        return await loop.run_in_executor(None, fetch_metrics_db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    return {"status": "success"}

# ================= Core Transcription Logic (App Main Flow) =================

async def transcribe_bytes_async(audio_bytes: bytes):
    url = "https://api.deepgram.com/v1/listen?model=nova-2&language=hi&detect_language=true&diarize=true&punctuate=true&utterances=true"
    headers = {"Authorization": "Token " + DEEPGRAM_API_KEY, "Content-Type": "audio/mp3"}
    
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(url, headers=headers, content=audio_bytes)
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
        "strengths": ["Strong point"],
        "improvements": ["Improvement point"]
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

        # Extract Name/Email from Firebase Token Payload safely
        uploader_name = "Admin"
        if user_info and isinstance(user_info, dict):
            email = user_info.get("email", "")
            name = user_info.get("name", "")
            if name:
                uploader_name = name
            elif email:
                uploader_name = email.split("@")[0]

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
                    "wpm": metrics.get("wpm", 0),
                    "duration": metrics.get("duration", 0),
                    "total_words": metrics.get("total_words", 0),
                    "created_at": created_time
                }
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, lambda: db.collection("audits").add(audit_data))
            except Exception as fe:
                print("❌ Firebase Write Error:", fe)

        return {"status": "success", "filename": file.filename, "data": {"metrics": metrics, "transcript": transcript, "evaluation": evaluation}}
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
    return {"results": results}

@app.get("/api/history")
async def get_history(limit: Optional[int] = None, user: dict = Depends(verify_firebase_token)):
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

        return await loop.run_in_executor(None, fetch_db)
    except Exception as e:
        print("❌ Firebase Fetch Error:", str(e))
        return []

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
        return {"status": "success", "message": "Audit record deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
