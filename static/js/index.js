        const state = {
            chats: [],
            activeChatId: null,
            activeChat: null,
            sending: false,
            voiceListening: false,
            voiceProcessing: false,
            voiceSupported: false,
            voiceWarmupStarted: false,
            pendingFiles: [],
            chatSearchQuery: "",
            theme: "dark",
            sidebarClosed: false,
            searchPanelOpen: false,
            historyMinimized: false,
            searchMeta: {
                limit: 80,
                min_score: 1.8,
                mode: "fuzzy",
            },
            statuses: {
                chatgpt: null,
                ollama: null,
            },
            ollamaModels: [],
            selectedOllamaModel: null,
        };

        const rootNode = document.documentElement;
        const sidebar = document.getElementById("sidebar");
        const searchPanel = document.getElementById("searchPanel");
        const historyPanel = document.getElementById("historyPanel");
        const chatList = document.getElementById("chatList");
        const chatCount = document.getElementById("chatCount");
        const chatSubtitle = document.getElementById("chatSubtitle");
        const chatTitle = document.getElementById("chatTitle");
        const chatgptStatus = document.getElementById("chatgptStatus");
        const ollamaStatus = document.getElementById("ollamaStatus");
        const chatgptPanel = document.getElementById("chatgptPanel");
        const ollamaPanel = document.getElementById("ollamaPanel");
        const ollamaModelSelect = document.getElementById("ollamaModelSelect");
        const composer = document.getElementById("composer");
        const composerHint = document.getElementById("composerHint");
        const attachmentList = document.getElementById("attachmentList");
        const chatFileInput = document.getElementById("chatFileInput");
        const fileUploadButton = document.getElementById("fileUploadButton");
        const voiceStatus = document.getElementById("voiceStatus");
        const voiceButton = document.getElementById("voiceButton");
        const sendButton = document.getElementById("sendButton");
        const newChatButton = document.getElementById("newChatButton");
        const searchToggleButton = document.getElementById("searchToggleButton");
        const historyToggleButton = document.getElementById("historyToggleButton");
        const themeToggle = document.getElementById("themeToggle");
        const sidebarHandleButton = document.getElementById("sidebarHandleButton");
        const chatSearchInput = document.getElementById("chatSearchInput");
        const toastContainer = document.getElementById("toastContainer");
        const initialShellPayloadNode = document.getElementById("initialShellPayload");
        const THEME_STORAGE_KEY = "uiTheme";
        const SIDEBAR_CLOSED_STORAGE_KEY = "sidebarClosed";
        const HISTORY_MINIMIZED_STORAGE_KEY = "historyMinimized";
        const OLLAMA_MODEL_STORAGE_KEY = "selectedOllamaModel";
        const OLLAMA_MODEL_EXPLICIT_STORAGE_KEY = "selectedOllamaModelExplicit";
        let chatSearchTimer = null;
        let chatListRequestToken = 0;
        let panelsRenderFrame = null;
        let voiceRecorder = null;
        const warmedOllamaModels = new Set();
        let browserWarmupStarted = false;

        function escapeHtml(value) {
            return String(value ?? "")
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#39;");
        }

        function renderText(text) {
            return escapeHtml(text).replace(/\n/g, "<br>");
        }

        function renderInlineMarkdown(text) {
            let html = escapeHtml(text || "");
            html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
            html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
            html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
            html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
            return html;
        }

        function renderMarkdown(text) {
            const source = String(text || "").replace(/\r\n/g, "\n").trim();
            if (!source) {
                return "";
            }

            const codeBlocks = [];
            const placeholderSource = source.replace(/```([\w-]*)\n([\s\S]*?)```/g, (_, language, code) => {
                const index = codeBlocks.length;
                codeBlocks.push({
                    language: escapeHtml(language || ""),
                    code: escapeHtml(code || ""),
                });
                return `@@CODEBLOCK_${index}@@`;
            });

            const lines = placeholderSource.split("\n");
            const blocks = [];
            let index = 0;

            while (index < lines.length) {
                const rawLine = lines[index];
                const line = rawLine.trimEnd();
                const trimmed = line.trim();

                if (!trimmed) {
                    index += 1;
                    continue;
                }

                const codeMatch = trimmed.match(/^@@CODEBLOCK_(\d+)@@$/);
                if (codeMatch) {
                    const codeBlock = codeBlocks[Number(codeMatch[1])];
                    blocks.push(`
                        <pre class="rich-code-block"><code class="${codeBlock.language ? `language-${codeBlock.language}` : ""}">${codeBlock.code}</code></pre>
                    `);
                    index += 1;
                    continue;
                }

                const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/);
                if (headingMatch) {
                    const level = headingMatch[1].length;
                    blocks.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
                    index += 1;
                    continue;
                }

                if (/^>\s+/.test(trimmed)) {
                    const quoteLines = [];
                    while (index < lines.length && /^>\s+/.test(lines[index].trim())) {
                        quoteLines.push(lines[index].trim().replace(/^>\s+/, ""));
                        index += 1;
                    }
                    blocks.push(`<blockquote>${quoteLines.map(renderInlineMarkdown).join("<br>")}</blockquote>`);
                    continue;
                }

                if (/^([-*]|\d+\.)\s+/.test(trimmed)) {
                    const ordered = /^\d+\./.test(trimmed);
                    const tag = ordered ? "ol" : "ul";
                    const items = [];
                    while (index < lines.length && /^([-*]|\d+\.)\s+/.test(lines[index].trim())) {
                        items.push(lines[index].trim().replace(/^([-*]|\d+\.)\s+/, ""));
                        index += 1;
                    }
                    blocks.push(`<${tag}>${items.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</${tag}>`);
                    continue;
                }

                const paragraphLines = [];
                while (index < lines.length) {
                    const candidate = lines[index].trim();
                    if (!candidate) {
                        index += 1;
                        break;
                    }
                    if (
                        /^@@CODEBLOCK_\d+@@$/.test(candidate)
                        || /^(#{1,3})\s+/.test(candidate)
                        || /^>\s+/.test(candidate)
                        || /^([-*]|\d+\.)\s+/.test(candidate)
                    ) {
                        break;
                    }
                    paragraphLines.push(lines[index].trim());
                    index += 1;
                }
                blocks.push(`<p>${renderInlineMarkdown(paragraphLines.join(" "))}</p>`);
            }

            return blocks.join("");
        }

        function showToast(message, kind = "info") {
            const palette = {
                info: "toast-info",
                success: "toast-success",
                error: "toast-error",
            };

            const toast = document.createElement("div");
            toast.className = `toast ${palette[kind] || palette.info}`;
            toast.textContent = message;
            toastContainer.appendChild(toast);

            setTimeout(() => {
                toast.classList.add("translate-y-1", "opacity-0", "transition");
                setTimeout(() => toast.remove(), 250);
            }, 2200);
        }

        function formatFileSize(sizeBytes) {
            const numericSize = Number(sizeBytes || 0);
            if (!numericSize) {
                return "";
            }
            if (numericSize < 1024) {
                return `${numericSize} B`;
            }
            if (numericSize < 1024 * 1024) {
                return `${(numericSize / 1024).toFixed(1)} KB`;
            }
            return `${(numericSize / (1024 * 1024)).toFixed(1)} MB`;
        }

        function fileIdentity(fileLike) {
            return [
                fileLike.name || "",
                fileLike.size || 0,
                fileLike.lastModified || 0,
            ].join("::");
        }

        function attachmentMetadataFromFile(file) {
            return {
                content_type: file.type || "",
                name: file.name,
                size_bytes: file.size || 0,
            };
        }

        function renderAttachmentChips(attachments, { removable = false } = {}) {
            const normalized = Array.isArray(attachments) ? attachments : [];
            if (normalized.length === 0) {
                return "";
            }

            return `
                <div class="turn-attachments">
                    ${normalized.map((attachment, index) => `
                        <span class="attachment-chip text-xs">
                            <span class="attachment-chip-name">${escapeHtml(attachment.name || "Attachment")}</span>
                            ${attachment.size_bytes ? `
                                <span class="attachment-chip-size">${escapeHtml(formatFileSize(attachment.size_bytes))}</span>
                            ` : ""}
                            ${removable ? `
                                <button
                                    type="button"
                                    class="attachment-chip-remove transition"
                                    data-action="remove-attachment"
                                    data-file-index="${index}"
                                    aria-label="Remove attachment"
                                    title="Remove attachment"
                                >
                                    ×
                                </button>
                            ` : ""}
                        </span>
                    `).join("")}
                </div>
            `;
        }

        function renderPendingAttachments() {
            if (!attachmentList) {
                return;
            }

            attachmentList.innerHTML = renderAttachmentChips(
                state.pendingFiles.map(attachmentMetadataFromFile),
                { removable: true }
            );
        }

        function schedulePanelsRender() {
            if (panelsRenderFrame !== null) {
                return;
            }

            const schedule = window.requestAnimationFrame || ((callback) => window.setTimeout(callback, 16));
            panelsRenderFrame = schedule(() => {
                panelsRenderFrame = null;
                renderPanels();
            });
        }

        function setVoiceStatus(message, mode = "idle") {
            if (!voiceStatus) {
                return;
            }

            voiceStatus.textContent = message;
            voiceStatus.className = "voice-status text-xs";
            if (mode === "listening") {
                voiceStatus.classList.add("is-listening");
            } else if (mode === "processing") {
                voiceStatus.classList.add("is-processing");
            } else if (mode === "ready") {
                voiceStatus.classList.add("is-ready");
            } else if (mode === "error") {
                voiceStatus.classList.add("is-error");
            } else {
                voiceStatus.classList.add("text-secondary");
            }
        }

        function renderVoiceButton() {
            if (!voiceButton) {
                return;
            }

            voiceButton.classList.remove("is-listening", "is-processing");
            voiceButton.disabled = !state.voiceSupported || state.voiceProcessing || state.sending;

            if (state.voiceListening) {
                voiceButton.classList.add("is-listening");
                voiceButton.setAttribute("aria-label", "Stop voice input");
                voiceButton.title = "Stop voice input";
                return;
            }

            if (state.voiceProcessing) {
                voiceButton.classList.add("is-processing");
                voiceButton.setAttribute("aria-label", "Transcribing voice input");
                voiceButton.title = "Transcribing voice input";
                return;
            }

            voiceButton.setAttribute("aria-label", "Start voice input");
            voiceButton.title = state.voiceSupported
                ? "Start voice input"
                : "Microphone recording is not supported in this browser";
        }

        function detectVoiceSupport() {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            return Boolean(
                voiceButton
                && navigator.mediaDevices
                && typeof navigator.mediaDevices.getUserMedia === "function"
                && AudioContextClass
            );
        }

        function mergeAudioChunks(chunks) {
            const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
            const merged = new Float32Array(totalLength);
            let offset = 0;
            for (const chunk of chunks) {
                merged.set(chunk, offset);
                offset += chunk.length;
            }
            return merged;
        }

        function writeAsciiString(view, offset, value) {
            for (let index = 0; index < value.length; index += 1) {
                view.setUint8(offset + index, value.charCodeAt(index));
            }
        }

        function encodeWav(samples, sampleRate) {
            const buffer = new ArrayBuffer(44 + samples.length * 2);
            const view = new DataView(buffer);

            writeAsciiString(view, 0, "RIFF");
            view.setUint32(4, 36 + samples.length * 2, true);
            writeAsciiString(view, 8, "WAVE");
            writeAsciiString(view, 12, "fmt ");
            view.setUint32(16, 16, true);
            view.setUint16(20, 1, true);
            view.setUint16(22, 1, true);
            view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * 2, true);
            view.setUint16(32, 2, true);
            view.setUint16(34, 16, true);
            writeAsciiString(view, 36, "data");
            view.setUint32(40, samples.length * 2, true);

            let offset = 44;
            for (const sample of samples) {
                const clamped = Math.max(-1, Math.min(1, sample));
                view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
                offset += 2;
            }

            return new Blob([view], { type: "audio/wav" });
        }

        function cleanupVoiceRecorder(recorder) {
            if (!recorder) {
                return;
            }

            try {
                recorder.processor.disconnect();
            } catch {}

            try {
                recorder.source.disconnect();
            } catch {}

            try {
                recorder.gainNode.disconnect();
            } catch {}

            try {
                recorder.stream.getTracks().forEach((track) => track.stop());
            } catch {}

            try {
                recorder.context.close();
            } catch {}
        }

        async function warmVoiceTranscriber() {
            if (state.voiceWarmupStarted) {
                return;
            }

            state.voiceWarmupStarted = true;
            try {
                await fetch("/api/transcribe/warmup", { method: "POST" });
            } catch {
                // The actual transcription request will surface any real error.
            }
        }

        async function startVoiceRecording() {
            if (!state.voiceSupported || state.voiceListening || state.voiceProcessing) {
                return;
            }

            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        channelCount: 1,
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                    },
                });
                const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                const context = new AudioContextClass();
                await context.resume();

                const source = context.createMediaStreamSource(stream);
                const processor = context.createScriptProcessor(4096, 1, 1);
                const gainNode = context.createGain();
                gainNode.gain.value = 0;

                const chunks = [];
                processor.onaudioprocess = (event) => {
                    if (!state.voiceListening) {
                        return;
                    }
                    const channel = event.inputBuffer.getChannelData(0);
                    chunks.push(new Float32Array(channel));
                };

                source.connect(processor);
                processor.connect(gainNode);
                gainNode.connect(context.destination);

                voiceRecorder = {
                    chunks,
                    context,
                    gainNode,
                    processor,
                    sampleRate: context.sampleRate,
                    source,
                    stream,
                };

                state.voiceListening = true;
                setVoiceStatus("Listening...", "listening");
                renderVoiceButton();
                warmVoiceTranscriber();
            } catch (error) {
                state.voiceListening = false;
                state.voiceProcessing = false;
                renderVoiceButton();
                setVoiceStatus("Microphone unavailable.", "error");
                showToast(
                    error?.name === "NotAllowedError"
                        ? "Microphone permission was denied."
                        : "Unable to access the microphone.",
                    "error"
                );
            }
        }

        function insertTranscriptIntoComposer(transcript) {
            const cleanTranscript = String(transcript || "").trim();
            if (!cleanTranscript) {
                throw new Error("Voice transcription was empty.");
            }

            const selectionStart = composer.selectionStart ?? composer.value.length;
            const selectionEnd = composer.selectionEnd ?? composer.value.length;
            const prefix = composer.value.slice(0, selectionStart);
            const suffix = composer.value.slice(selectionEnd);
            const needsLeadingSpace = prefix.length > 0 && !/\s$/.test(prefix);
            const needsTrailingSpace = suffix.length > 0 && !/^\s/.test(suffix);
            const insertedText = `${needsLeadingSpace ? " " : ""}${cleanTranscript}${needsTrailingSpace ? " " : ""}`;

            composer.value = `${prefix}${insertedText}${suffix}`;
            const caretPosition = prefix.length + insertedText.length;
            composer.focus();
            composer.setSelectionRange(caretPosition, caretPosition);
        }

        async function stopVoiceRecording() {
            if (!voiceRecorder || !state.voiceListening) {
                return;
            }

            state.voiceListening = false;
            state.voiceProcessing = true;
            setVoiceStatus("Transcribing locally...", "processing");
            renderVoiceButton();

            const recorder = voiceRecorder;
            voiceRecorder = null;

            try {
                cleanupVoiceRecorder(recorder);
                const samples = mergeAudioChunks(recorder.chunks);
                if (samples.length === 0) {
                    throw new Error("No audio was captured. Please try again.");
                }

                const audioBlob = encodeWav(samples, recorder.sampleRate);
                const formData = new FormData();
                formData.append("audio", audioBlob, "voice-input.wav");

                const response = await fetch("/api/transcribe", {
                    method: "POST",
                    body: formData,
                });
                const payload = await response.json();
                if (!response.ok) {
                    throw new Error(payload.error || "Unable to transcribe the recording.");
                }

                insertTranscriptIntoComposer(payload.text || "");
                setVoiceStatus("Transcript inserted. You can edit before sending.", "ready");
                showToast("Voice transcription added to the composer.", "success");
            } catch (error) {
                setVoiceStatus("Voice transcription failed.", "error");
                showToast(error?.message || "Unable to transcribe voice input.", "error");
            } finally {
                state.voiceProcessing = false;
                renderVoiceButton();
            }
        }

        async function toggleVoiceRecording() {
            if (!state.voiceSupported) {
                showToast("Microphone recording is not supported in this browser.", "error");
                return;
            }

            if (state.voiceProcessing || state.sending) {
                return;
            }

            if (state.voiceListening) {
                await stopVoiceRecording();
                return;
            }

            await startVoiceRecording();
        }

        function addPendingFiles(fileList) {
            const incomingFiles = Array.from(fileList || []);
            if (incomingFiles.length === 0) {
                return;
            }

            const existingKeys = new Set(state.pendingFiles.map(fileIdentity));
            for (const file of incomingFiles) {
                const fileKey = fileIdentity(file);
                if (existingKeys.has(fileKey)) {
                    continue;
                }
                existingKeys.add(fileKey);
                state.pendingFiles.push(file);
            }

            renderPendingAttachments();
        }

        function renderSidebarVisibility() {
            sidebar.classList.toggle("sidebar-collapsed", state.sidebarClosed);
            localStorage.setItem(SIDEBAR_CLOSED_STORAGE_KEY, state.sidebarClosed ? "1" : "0");
            sidebarHandleButton.setAttribute("aria-label", state.sidebarClosed ? "Open sidebar" : "Close sidebar");
            sidebarHandleButton.innerHTML = state.sidebarClosed
                ? `
                    <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <rect x="3.5" y="4.5" width="17" height="15" rx="2.5"></rect>
                        <path d="M9 4.5v15"></path>
                    </svg>
                `
                : `
                    <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <rect x="3.5" y="4.5" width="17" height="15" rx="2.5"></rect>
                        <path d="M15 4.5v15"></path>
                    </svg>
                `;
        }

        function renderToggleButton(button, isActive) {
            button.className = isActive
                ? "sidebar-action is-active transition"
                : "sidebar-action transition";
        }

        function renderSidebarPanels() {
            const showSearchPanel = state.searchPanelOpen || Boolean(state.chatSearchQuery);
            searchPanel.classList.toggle("panel-hidden", !showSearchPanel);
            historyPanel.classList.toggle("panel-hidden", state.historyMinimized);
            renderToggleButton(searchToggleButton, showSearchPanel);
            renderToggleButton(historyToggleButton, !state.historyMinimized);
            localStorage.setItem(HISTORY_MINIMIZED_STORAGE_KEY, state.historyMinimized ? "1" : "0");
        }

        function getStoredTheme() {
            const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
            return storedTheme === "light" ? "light" : "dark";
        }

        function renderThemeToggle() {
            themeToggle.textContent = state.theme === "dark" ? "Light Mode" : "Dark Mode";
            themeToggle.setAttribute("aria-pressed", String(state.theme === "dark"));
        }

        function applyTheme(themeName) {
            state.theme = themeName === "light" ? "light" : "dark";
            rootNode.dataset.theme = state.theme;
            localStorage.setItem(THEME_STORAGE_KEY, state.theme);
            renderThemeToggle();
        }

        function createDraftChat() {
            return {
                id: null,
                title: "New Chat",
                turns: [],
                messages: [],
            };
        }

        function setChatInUrl(chatId) {
            const url = new URL(window.location.href);
            if (chatId) {
                url.searchParams.set("chat", chatId);
            } else {
                url.searchParams.delete("chat");
            }
            window.history.replaceState({}, "", url);
        }

        function openDraftChat({ focusComposer = false } = {}) {
            state.activeChatId = null;
            state.activeChat = createDraftChat();
            setChatInUrl(null);
            renderChats();
            renderPanels();
            if (focusComposer) {
                composer.focus();
            }
        }

        function getPreferredModel() {
            return localStorage.getItem(OLLAMA_MODEL_STORAGE_KEY);
        }

        function hasExplicitPreferredModel() {
            return localStorage.getItem(OLLAMA_MODEL_EXPLICIT_STORAGE_KEY) === "1";
        }

        function setPreferredModel(modelName, { explicit = false } = {}) {
            if (modelName) {
                localStorage.setItem(OLLAMA_MODEL_STORAGE_KEY, modelName);
                if (explicit) {
                    localStorage.setItem(OLLAMA_MODEL_EXPLICIT_STORAGE_KEY, "1");
                } else if (!hasExplicitPreferredModel()) {
                    localStorage.removeItem(OLLAMA_MODEL_EXPLICIT_STORAGE_KEY);
                }
            } else {
                localStorage.removeItem(OLLAMA_MODEL_STORAGE_KEY);
                localStorage.removeItem(OLLAMA_MODEL_EXPLICIT_STORAGE_KEY);
            }
        }

        function availableOllamaModelNames() {
            const stateModelNames = state.ollamaModels
                .map((model) => model?.name || "")
                .filter(Boolean);
            if (stateModelNames.length > 0) {
                return stateModelNames;
            }

            if (!ollamaModelSelect) {
                return [];
            }

            return Array.from(ollamaModelSelect.options || [])
                .map((option) => option.value || "")
                .filter(Boolean);
        }

        function ensureSelectedOllamaModel(fallbackModel = "") {
            const modelNames = availableOllamaModelNames();
            const domValue = ollamaModelSelect?.value || "";
            const preferredModel = getPreferredModel();
            const preferredModelIsExplicit = hasExplicitPreferredModel();
            const requestedFallback = String(fallbackModel || "").trim();

            let resolvedModel = "";
            if (modelNames.includes(state.selectedOllamaModel)) {
                resolvedModel = state.selectedOllamaModel;
            } else if (preferredModelIsExplicit && modelNames.includes(preferredModel)) {
                resolvedModel = preferredModel;
            } else if (modelNames.includes(requestedFallback)) {
                resolvedModel = requestedFallback;
            } else if (modelNames.includes(domValue)) {
                resolvedModel = domValue;
            } else if (modelNames.includes(preferredModel)) {
                resolvedModel = preferredModel;
            } else {
                resolvedModel = modelNames[0] || "";
            }

            state.selectedOllamaModel = resolvedModel || null;

            if (ollamaModelSelect) {
                ollamaModelSelect.disabled = modelNames.length === 0;
                if (state.selectedOllamaModel) {
                    ollamaModelSelect.value = state.selectedOllamaModel;
                }
            }

            setPreferredModel(state.selectedOllamaModel, { explicit: preferredModelIsExplicit });
            return state.selectedOllamaModel;
        }

        async function warmOllamaModel(modelName) {
            const resolvedModel = String(modelName || "").trim();
            if (!resolvedModel || warmedOllamaModels.has(resolvedModel)) {
                return;
            }

            warmedOllamaModels.add(resolvedModel);
            try {
                const response = await fetch("/api/ollama/warmup", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ model: resolvedModel }),
                });
                if (!response.ok) {
                    warmedOllamaModels.delete(resolvedModel);
                    return;
                }

                const payload = await response.json();
                if (payload?.status || payload?.ollama_models) {
                    applyShellPayload(payload);
                }
            } catch {
                warmedOllamaModels.delete(resolvedModel);
            }
        }

        async function warmChatgptBrowser() {
            if (browserWarmupStarted) {
                return;
            }

            browserWarmupStarted = true;
            try {
                const response = await fetch("/api/browser/warmup", {
                    method: "POST",
                });
                if (!response.ok) {
                    browserWarmupStarted = false;
                    return;
                }

                const payload = await response.json();
                if (payload?.status) {
                    applyShellPayload(payload);
                }
            } catch {
                browserWarmupStarted = false;
            }
        }

        function updateStatusBadge(element, status, activeClasses, idleClasses) {
            const connected = Boolean(status?.connected);
            element.textContent = status?.message || "Unavailable";
            element.className = connected
                ? `status-badge rounded-full px-3 py-1 text-sm ${activeClasses}`
                : `status-badge rounded-full px-3 py-1 text-sm ${idleClasses}`;
        }

        function getProviderLabel(providerKey) {
            if (providerKey === "chatgpt") {
                return "ChatGPT";
            }

            return state.selectedOllamaModel || "Ollama";
        }

        function describeProviders(providerKeys) {
            const labels = Array.from(new Set(providerKeys || []))
                .filter(Boolean)
                .map(getProviderLabel);

            if (labels.length === 0) {
                return "No providers";
            }
            if (labels.length === 1) {
                return labels[0];
            }
            if (labels.length === 2) {
                return `${labels[0]} and ${labels[1]}`;
            }
            return `${labels.slice(0, -1).join(", ")}, and ${labels[labels.length - 1]}`;
        }

        function getProviderAvailabilityForSend() {
            const availability = {
                active: [],
                unavailable: {},
                ollamaModel: null,
            };

            if (state.statuses.chatgpt?.connected) {
                availability.active.push("chatgpt");
            } else {
                availability.unavailable.chatgpt = state.statuses.chatgpt?.message || "ChatGPT is unavailable.";
            }

            if (state.statuses.ollama?.connected) {
                const selectedModel = ensureSelectedOllamaModel();
                if (selectedModel) {
                    availability.active.push("ollama");
                    availability.ollamaModel = selectedModel;
                } else {
                    availability.unavailable.ollama = "Pick an Ollama model first.";
                }
            } else {
                availability.unavailable.ollama = state.statuses.ollama?.message || "Ollama is unavailable.";
            }

            return availability;
        }

        function getIdleSendButtonLabel() {
            const availability = getProviderAvailabilityForSend();
            if (availability.active.length >= 2) {
                return "Send to Both";
            }
            if (availability.active.length === 1) {
                return `Send to ${describeProviders(availability.active)}`;
            }
            return "Send";
        }

        function getIdleComposerHint() {
            const availability = getProviderAvailabilityForSend();
            if (availability.active.length >= 2) {
                return "Shift + Enter for a new line. The same prompt goes to both panels.";
            }
            if (availability.active.length === 1) {
                return `Shift + Enter for a new line. The prompt will go to ${describeProviders(availability.active)} only until the other provider is ready.`;
            }
            return "Shift + Enter for a new line. Start ChatGPT or Ollama to send prompts.";
        }

        function renderComposerAvailability() {
            if (state.sending) {
                return;
            }

            sendButton.textContent = getIdleSendButtonLabel();
            composerHint.textContent = getIdleComposerHint();
        }

        function applyShellPayload(payload) {
            state.statuses = payload.status || state.statuses;
            state.ollamaModels = payload.ollama_models || [];
            if (payload.search_meta) {
                state.searchMeta = payload.search_meta;
            }

            updateStatusBadge(
                chatgptStatus,
                state.statuses.chatgpt,
                "status-connected",
                "status-idle"
            );
            updateStatusBadge(
                ollamaStatus,
                state.statuses.ollama,
                "status-local",
                "status-idle"
            );

            const modelNames = state.ollamaModels.map((model) => model.name);
            const defaultModel = payload.default_ollama_model || modelNames[0] || "";
            renderModelSelect();
            const selectedModel = ensureSelectedOllamaModel(defaultModel);
            warmOllamaModel(selectedModel);
            if (state.statuses.chatgpt?.connected) {
                warmChatgptBrowser();
            }
            renderComposerAvailability();
        }

        function renderModelSelect() {
            const modelNames = state.ollamaModels.map((model) => model.name);
            ollamaModelSelect.innerHTML = "";

            if (modelNames.length === 0) {
                const option = document.createElement("option");
                option.value = "";
                option.textContent = "No local models found";
                ollamaModelSelect.appendChild(option);
                ollamaModelSelect.disabled = true;
                return;
            }

            ollamaModelSelect.disabled = false;
            for (const modelName of modelNames) {
                const option = document.createElement("option");
                option.value = modelName;
                option.textContent = modelName;
                if (modelName === state.selectedOllamaModel) {
                    option.selected = true;
                }
                ollamaModelSelect.appendChild(option);
            }

            ensureSelectedOllamaModel(modelNames[0] || "");
        }

        function renderChats() {
            chatCount.textContent = String(state.chats.length);
            chatList.innerHTML = "";
            chatSubtitle.textContent = state.chatSearchQuery
                ? `Closest fuzzy matches across titles, prompts, ChatGPT, and local replies`
                : "Fuzzy search across titles, prompts, and replies. Spaces are optional.";

            if (state.chats.length === 0) {
                chatList.innerHTML = `
                    <div class="rounded-2xl border border-dashed border-soft p-4 text-sm text-secondary">
                        ${state.chatSearchQuery
                            ? `No close matches found for "${escapeHtml(state.chatSearchQuery)}". Try fewer words or a shorter phrase.`
                            : "No chats yet. Start one and both panels will save locally."
                        }
                    </div>
                `;
                return;
            }

            for (const chat of state.chats) {
                const showSearchContext = Boolean(state.chatSearchQuery);
                const item = document.createElement("div");
                item.className = `rounded-2xl border ${
                    chat.id === state.activeChatId
                        ? "chat-item-active"
                        : "chat-item-idle"
                } transition`;

                item.innerHTML = `
                    <div class="history-card-body flex items-start gap-3">
                        <button class="min-w-0 flex-1 text-left" data-action="open-chat" data-chat-id="${chat.id}">
                            <div class="truncate font-medium text-primary">${escapeHtml(chat.title)}</div>
                            ${showSearchContext ? `
                                <div class="mt-1 truncate text-xs text-secondary">${escapeHtml(chat.preview || "")}</div>
                            ` : ""}
                            ${showSearchContext && chat.search_label ? `
                                <div class="mt-2 flex items-center gap-2 text-xs text-muted">
                                    <span class="match-badge">${escapeHtml(chat.search_label)}</span>
                                    <span>closest match</span>
                                </div>
                            ` : ""}
                        </button>
                        <button
                            class="delete-button rounded-lg transition"
                            data-action="delete-chat"
                            data-chat-id="${chat.id}"
                            title="Delete chat"
                            aria-label="Delete chat"
                        >
                            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                <path d="M4 7h16"></path>
                                <path d="M9 7V4.8c0-.44.36-.8.8-.8h4.4c.44 0 .8.36.8.8V7"></path>
                                <path d="M18 7l-1 11.2c-.05.45-.43.8-.88.8H7.88c-.45 0-.83-.35-.88-.8L6 7"></path>
                                <path d="M10 11v4.5"></path>
                                <path d="M14 11v4.5"></path>
                            </svg>
                        </button>
                    </div>
                `;
                chatList.appendChild(item);
            }
        }

        function makePanelEmptyState(title, detail) {
            return `
                <div class="flex h-full min-h-[260px] items-center justify-center">
                    <div class="max-w-md text-center text-secondary">
                        <h3 class="text-2xl font-semibold text-primary">${escapeHtml(title)}</h3>
                        <p class="mt-2 text-sm leading-6">${escapeHtml(detail)}</p>
                    </div>
                </div>
            `;
        }

        function getTurnResponse(turn, providerKey) {
            if (providerKey === "chatgpt") {
                return turn.chatgpt || null;
            }

            const selectedModel = state.selectedOllamaModel || "";
            const selectedResponse = (turn.ollama && turn.ollama[selectedModel]) || null;
            if (selectedResponse) {
                return selectedResponse;
            }

            const fallbackResponses = Array.isArray(turn.responses)
                ? turn.responses.filter((response) => response?.provider === "ollama" && response?.content)
                : [];
            if (fallbackResponses.length > 0) {
                return fallbackResponses[0];
            }

            const mappedResponses = Object.values(turn.ollama || {}).filter((response) => response?.content);
            return mappedResponses[0] || null;
        }

        function getPendingState(turn, providerKey) {
            return turn.pending?.[providerKey] || null;
        }

        function getTurnError(turn, providerKey) {
            return turn.errors?.[providerKey] || null;
        }

        function responseActions(turn, providerKey, response) {
            if (!response?.content) {
                return "";
            }

            return `
                <div class="mt-4 flex items-center gap-2">
                    <button
                        class="secondary-button rounded-lg px-3 py-1.5 text-xs font-medium transition"
                        data-action="copy-response"
                        data-turn-id="${turn.id}"
                        data-provider="${providerKey}"
                    >
                        Copy
                    </button>
                </div>
            `;
        }

        function renderTurnCard(turn, providerKey) {
            const response = getTurnResponse(turn, providerKey);
            const pendingState = getPendingState(turn, providerKey);
            const errorText = getTurnError(turn, providerKey);
            const modelLabel = providerKey === "ollama"
                ? (response?.model_name || state.selectedOllamaModel || "Local model")
                : "ChatGPT";
            const promptAttachments = Array.isArray(turn.prompt?.attachments) ? turn.prompt.attachments : [];

            let responseBody = `
                <div class="turn-block surface-muted mt-3 rounded-2xl border border-soft text-sm leading-7 text-primary">
                    <div class="mb-3 text-xs uppercase tracking-[0.24em] text-muted">${escapeHtml(modelLabel)}</div>
                    <div class="rich-text">${renderMarkdown(response?.content || "")}</div>
                    ${responseActions(turn, providerKey, response)}
                </div>
            `;

            if (!response && pendingState) {
                responseBody = `
                    <div class="turn-block surface-muted mt-3 rounded-2xl border border-dashed border-soft text-sm text-secondary">
                        <div class="flex items-center gap-3">
                            <div class="h-2.5 w-2.5 animate-pulse rounded-full bg-accent"></div>
                            <span>${providerKey === "chatgpt" ? "ChatGPT is thinking..." : `${escapeHtml(modelLabel)} is thinking...`}</span>
                        </div>
                    </div>
                `;
            }

            if (errorText) {
                responseBody = `
                    <div class="turn-block error-box mt-3 rounded-2xl text-sm">
                        ${renderText(errorText)}
                    </div>
                `;
            }

            return `
                <article class="turn-card surface-card rounded-[1.5rem] border border-soft">
                    <div class="text-xs uppercase tracking-[0.24em] text-muted">Prompt</div>
                    <div class="turn-block surface-subtle mt-3 rounded-2xl text-sm leading-7 text-primary">
                        ${renderAttachmentChips(promptAttachments)}
                        ${renderText(turn.prompt?.content || "")}
                    </div>
                    ${responseBody}
                </article>
            `;
        }

        function renderPanels() {
            const chat = state.activeChat;
            const turns = chat?.turns || [];
            chatTitle.textContent = chat?.title || "Local Dual Chat Desktop";

            if (!chat) {
                chatgptPanel.innerHTML = makePanelEmptyState(
                    "Start a new conversation",
                    "Create a chat from the sidebar, then send one prompt to both engines."
                );
                ollamaPanel.innerHTML = makePanelEmptyState(
                    "Choose a local model",
                    "Pick an Ollama model above and send the same prompt to compare answers side by side."
                );
                return;
            }

            if (turns.length === 0) {
                chatgptPanel.innerHTML = makePanelEmptyState(
                    "ChatGPT panel is ready",
                    "The next prompt will appear here and stream in from the Brave-connected ChatGPT tab."
                );
                ollamaPanel.innerHTML = makePanelEmptyState(
                    "Local model panel is ready",
                    "The selected Ollama model will answer here with its own saved local history."
                );
                return;
            }

            chatgptPanel.innerHTML = turns.map((turn) => renderTurnCard(turn, "chatgpt")).join("");
            ollamaPanel.innerHTML = turns.map((turn) => renderTurnCard(turn, "ollama")).join("");
            chatgptPanel.scrollTop = chatgptPanel.scrollHeight;
            ollamaPanel.scrollTop = ollamaPanel.scrollHeight;
        }

        async function copyText(text, successMessage) {
            try {
                await navigator.clipboard.writeText(text);
                showToast(successMessage, "success");
            } catch {
                showToast("Clipboard copy failed.", "error");
            }
        }

        function findTurn(turnId) {
            return state.activeChat?.turns?.find((turn) => String(turn.id) === String(turnId)) || null;
        }

        function findResponseText(turnId, providerKey) {
            const turn = findTurn(turnId);
            if (!turn) {
                return "";
            }
            return getTurnResponse(turn, providerKey)?.content || "";
        }

        function ensureActiveChatShell() {
            if (!state.activeChat) {
                state.activeChat = createDraftChat();
                state.activeChat.id = state.activeChatId;
            }
        }

        function addOptimisticTurn(promptText, attachments = [], activeProviders = ["chatgpt", "ollama"], unavailableProviders = {}) {
            ensureActiveChatShell();
            const turnId = `pending-${Date.now()}-${Math.random().toString(16).slice(2)}`;
            const optimisticTurn = {
                id: turnId,
                prompt: {
                    id: turnId,
                    role: "user",
                    content: promptText,
                    attachments,
                },
                chatgpt: null,
                ollama: {},
                activeProviders: [...activeProviders],
                pending: Object.fromEntries(
                    activeProviders.map((provider) => [provider, "thinking"])
                ),
                errors: { ...unavailableProviders },
            };

            state.activeChat.turns.push(optimisticTurn);
            if (state.activeChat.title === "New Chat") {
                state.activeChat.title = promptText.slice(0, 60) || "New Chat";
            }
            renderPanels();
            return optimisticTurn;
        }

        function replaceTurnId(oldTurnId, newTurnId) {
            const turn = findTurn(oldTurnId);
            if (!turn) {
                return;
            }
            turn.id = newTurnId;
            if (turn.prompt) {
                turn.prompt.turn_id = newTurnId;
            }
            if (turn.chatgpt) {
                turn.chatgpt.turn_id = newTurnId;
            }
            for (const value of Object.values(turn.ollama || {})) {
                value.turn_id = newTurnId;
            }
        }

        async function loadChats() {
            const requestToken = ++chatListRequestToken;
            const query = state.chatSearchQuery.trim();
            const params = new URLSearchParams();
            if (query) {
                params.set("q", query);
            }
            params.set("limit", String(state.searchMeta.limit || 80));
            params.set("min_score", String(state.searchMeta.min_score || 1.8));
            const requestUrl = `/api/chats?${params.toString()}`;
            const response = await fetch(requestUrl);
            const payload = await response.json();
            if (requestToken !== chatListRequestToken) {
                return payload;
            }

            applyShellPayload(payload);
            state.chats = payload.chats || [];
            renderChats();
            return payload;
        }

        async function loadChat(chatId) {
            const response = await fetch(`/api/chats/${chatId}`);
            if (!response.ok) {
                showToast("Unable to load chat.", "error");
                return;
            }

            const payload = await response.json();
            applyShellPayload(payload);
            state.activeChatId = payload.chat.id;
            state.activeChat = payload.chat;
            setChatInUrl(payload.chat.id);
            renderChats();
            renderPanels();
        }

        function createNewChat() {
            openDraftChat({ focusComposer: true });
        }

        async function deleteChat(chatId) {
            const confirmed = window.confirm("Delete this chat permanently?");
            if (!confirmed) {
                return;
            }

            const response = await fetch(`/api/chats/${chatId}`, { method: "DELETE" });
            const payload = await response.json();
            if (!response.ok) {
                showToast(payload.error || "Unable to delete chat.", "error");
                return;
            }

            applyShellPayload(payload);
            showToast("Chat deleted.", "success");
            await loadChats();

            if (state.activeChatId === chatId) {
                openDraftChat();
                return;
            }

            renderPanels();
        }

        async function parseStreamingResponse(response, onEvent) {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { value, done } = await reader.read();
                if (done) {
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed) {
                        continue;
                    }
                    onEvent(JSON.parse(trimmed));
                }
            }

            const finalChunk = buffer.trim();
            if (finalChunk) {
                onEvent(JSON.parse(finalChunk));
            }
        }

        function applyStreamEvent(event, optimisticTurn) {
            if (event.status || event.ollama_models) {
                applyShellPayload(event);
            }

            if (event.type === "start") {
                if (event.chat_id) {
                    state.activeChatId = event.chat_id;
                    if (state.activeChat) {
                        state.activeChat.id = event.chat_id;
                    }
                    setChatInUrl(event.chat_id);
                }

                if (event.turn_id && optimisticTurn.id !== event.turn_id) {
                    replaceTurnId(optimisticTurn.id, event.turn_id);
                    optimisticTurn = findTurn(event.turn_id) || optimisticTurn;
                }

                const startedTurn = findTurn(event.turn_id || optimisticTurn.id) || optimisticTurn;
                if (Array.isArray(event.active_providers)) {
                    startedTurn.activeProviders = [...event.active_providers];
                    startedTurn.pending = Object.fromEntries(
                        event.active_providers.map((provider) => [provider, "thinking"])
                    );
                }
                if (event.unavailable_providers && typeof event.unavailable_providers === "object") {
                    startedTurn.errors = {
                        ...(startedTurn.errors || {}),
                        ...event.unavailable_providers,
                    };
                }
                schedulePanelsRender();
                return startedTurn;
            }

            const turnId = event.turn_id || optimisticTurn.id;
            const turn = findTurn(turnId) || optimisticTurn;
            if (!turn.pending) {
                turn.pending = {};
            }
            if (!turn.errors) {
                turn.errors = {};
            }

            if (event.type === "provider_status") {
                turn.pending[event.provider] = event.state || "thinking";
            }

            if (event.type === "provider_delta") {
                if (event.provider === "chatgpt") {
                    turn.chatgpt = {
                        id: `live-chatgpt-${turnId}`,
                        role: "assistant",
                        provider: "chatgpt",
                        model_name: "ChatGPT",
                        turn_id: turnId,
                        content: event.content || "",
                    };
                    turn.pending.chatgpt = "streaming";
                }

                if (event.provider === "ollama") {
                    const modelName = event.model_name || state.selectedOllamaModel || "default";
                    if (!turn.ollama) {
                        turn.ollama = {};
                    }
                    turn.ollama[modelName] = {
                        id: `live-ollama-${turnId}-${modelName}`,
                        role: "assistant",
                        provider: "ollama",
                        model_name: modelName,
                        turn_id: turnId,
                        content: event.content || "",
                    };
                    turn.pending.ollama = "streaming";
                }
            }

            if (event.type === "provider_final" && event.message) {
                if (event.provider === "chatgpt") {
                    turn.chatgpt = event.message;
                    delete turn.pending.chatgpt;
                }

                if (event.provider === "ollama") {
                    const modelName = event.model_name || event.message.model_name || state.selectedOllamaModel || "default";
                    if (!turn.ollama) {
                        turn.ollama = {};
                    }
                    turn.ollama[modelName] = event.message;
                    delete turn.pending.ollama;
                }
            }

            if (event.type === "provider_error") {
                turn.errors[event.provider] = event.error || "Unknown error.";
                delete turn.pending[event.provider];
            }

            if (event.type === "provider_done") {
                delete turn.pending[event.provider];
            }

            if (event.type === "complete" && event.chat) {
                const preservedErrors = { ...(turn.errors || {}) };
                state.activeChat = event.chat;
                state.activeChatId = event.chat.id;
                setChatInUrl(event.chat.id);

                const refreshedTurn = findTurn(turnId);
                if (refreshedTurn && Object.keys(preservedErrors).length > 0) {
                    refreshedTurn.errors = {
                        ...(refreshedTurn.errors || {}),
                        ...preservedErrors,
                    };
                }
            }

            schedulePanelsRender();
            return turn;
        }

        async function handleSend() {
            const message = composer.value.trim();
            const pendingFiles = [...state.pendingFiles];
            const hasAttachments = pendingFiles.length > 0;
            if ((!message && !hasAttachments) || state.sending) {
                return;
            }

            if (state.voiceListening || state.voiceProcessing) {
                showToast("Finish the voice recording first.", "error");
                return;
            }

            const providerAvailability = getProviderAvailabilityForSend();
            const activeProviders = providerAvailability.active;
            const unavailableProviders = providerAvailability.unavailable;
            const selectedModel = providerAvailability.ollamaModel || "";

            if (activeProviders.length === 0) {
                showToast(
                    [
                        unavailableProviders.chatgpt,
                        unavailableProviders.ollama,
                    ].filter(Boolean).join(" "),
                    "error"
                );
                return;
            }

            const effectiveMessage = message || (
                hasAttachments
                    ? (pendingFiles.length === 1
                        ? "Please analyze the attached file."
                        : "Please analyze the attached files.")
                    : ""
            );

            state.sending = true;
            sendButton.disabled = true;
            sendButton.textContent = activeProviders.length === 1
                ? `Sending to ${describeProviders(activeProviders)}...`
                : "Streaming...";
            composerHint.textContent = activeProviders.length === 1
                ? `${describeProviders(activeProviders)} is working...`
                : "Both providers are working...";
            renderVoiceButton();
            composer.value = "";
            state.pendingFiles = [];
            renderPendingAttachments();

            const optimisticTurn = addOptimisticTurn(
                effectiveMessage,
                pendingFiles.map(attachmentMetadataFromFile),
                activeProviders,
                unavailableProviders
            );

            try {
                const body = new FormData();
                body.append("chat_id", state.activeChatId || "");
                body.append("message", effectiveMessage);
                body.append("ollama_model", selectedModel);
                for (const file of pendingFiles) {
                    body.append("attachments", file, file.name);
                }

                const response = await fetch("/api/send", {
                    method: "POST",
                    body,
                });

                if (!response.ok) {
                    let errorMessage = "Request failed.";
                    try {
                        const payload = await response.json();
                        applyShellPayload(payload);
                        errorMessage = payload.error || errorMessage;
                    } catch {
                        // Keep the fallback message.
                    }

                    optimisticTurn.errors.chatgpt = errorMessage;
                    optimisticTurn.errors.ollama = errorMessage;
                    delete optimisticTurn.pending.chatgpt;
                    delete optimisticTurn.pending.ollama;
                    state.pendingFiles = pendingFiles;
                    renderPendingAttachments();
                    renderPanels();
                    showToast(errorMessage, "error");
                    return;
                }

                let workingTurn = optimisticTurn;
                await parseStreamingResponse(response, (event) => {
                    workingTurn = applyStreamEvent(event, workingTurn);
                });

                await loadChats();
                renderChats();
                renderPanels();
                const readyProviders = workingTurn.activeProviders || activeProviders;
                showToast(
                    readyProviders.length > 1
                        ? `${describeProviders(readyProviders)} responses are ready.`
                        : "Response is ready.",
                    "success"
                );
            } catch (error) {
                optimisticTurn.errors.chatgpt = error.message || "Unable to reach the backend.";
                optimisticTurn.errors.ollama = error.message || "Unable to reach the backend.";
                delete optimisticTurn.pending.chatgpt;
                delete optimisticTurn.pending.ollama;
                state.pendingFiles = pendingFiles;
                renderPendingAttachments();
                renderPanels();
                showToast("Unable to send the prompt.", "error");
            } finally {
                state.sending = false;
                sendButton.disabled = false;
                renderVoiceButton();
                renderComposerAvailability();
                composer.focus();
            }
        }

        chatList.addEventListener("click", async (event) => {
            const button = event.target.closest("[data-action]");
            if (!button) {
                return;
            }

            const action = button.dataset.action;
            const chatId = button.dataset.chatId;
            if (!chatId) {
                return;
            }

            if (action === "open-chat") {
                await loadChat(chatId);
            } else if (action === "delete-chat") {
                await deleteChat(chatId);
            }
        });

        function bindCopyHandler(panelElement, providerKey) {
            panelElement.addEventListener("click", async (event) => {
                const button = event.target.closest("[data-action='copy-response']");
                if (!button) {
                    return;
                }

                const turnId = button.dataset.turnId;
                const text = findResponseText(turnId, providerKey);
                if (!text) {
                    showToast("Nothing to copy yet.", "error");
                    return;
                }

                const original = button.textContent;
                await copyText(text, "Copied response to clipboard.");
                button.textContent = "Copied!";
                setTimeout(() => {
                    button.textContent = original;
                }, 1200);
            });
        }

        bindCopyHandler(chatgptPanel, "chatgpt");
        bindCopyHandler(ollamaPanel, "ollama");

        attachmentList.addEventListener("click", (event) => {
            const removeButton = event.target.closest("[data-action='remove-attachment']");
            if (!removeButton) {
                return;
            }

            const fileIndex = Number(removeButton.dataset.fileIndex || "-1");
            if (Number.isNaN(fileIndex) || fileIndex < 0 || fileIndex >= state.pendingFiles.length) {
                return;
            }

            state.pendingFiles.splice(fileIndex, 1);
            renderPendingAttachments();
        });

        ollamaModelSelect.addEventListener("change", () => {
            state.selectedOllamaModel = ollamaModelSelect.value || null;
            setPreferredModel(state.selectedOllamaModel, { explicit: true });
            warmOllamaModel(state.selectedOllamaModel);
            renderPanels();
        });

        searchToggleButton.addEventListener("click", () => {
            if (state.sidebarClosed) {
                state.sidebarClosed = false;
                state.searchPanelOpen = true;
                state.historyMinimized = false;
            } else {
                state.searchPanelOpen = !state.searchPanelOpen;
                if (state.searchPanelOpen) {
                    state.historyMinimized = false;
                }
            }
            renderSidebarVisibility();
            renderSidebarPanels();
            if (state.searchPanelOpen) {
                chatSearchInput.focus();
            }
        });

        historyToggleButton.addEventListener("click", () => {
            if (state.sidebarClosed) {
                state.sidebarClosed = false;
                state.historyMinimized = false;
                state.searchPanelOpen = false;
            } else {
                state.historyMinimized = !state.historyMinimized;
                if (!state.historyMinimized) {
                    state.searchPanelOpen = false;
                }
            }
            renderSidebarVisibility();
            renderSidebarPanels();
        });

        themeToggle.addEventListener("click", () => {
            applyTheme(state.theme === "dark" ? "light" : "dark");
        });

        sidebarHandleButton.addEventListener("click", () => {
            state.sidebarClosed = !state.sidebarClosed;
            if (state.sidebarClosed) {
                state.searchPanelOpen = false;
            }
            renderSidebarVisibility();
            renderSidebarPanels();
        });

        chatSearchInput.addEventListener("input", () => {
            const normalizedValue = chatSearchInput.value.replace(/\s+/g, " ");
            chatSearchInput.value = normalizedValue;
            state.chatSearchQuery = normalizedValue.trim();
            if (state.chatSearchQuery) {
                state.sidebarClosed = false;
                state.searchPanelOpen = true;
            }
            renderSidebarVisibility();
            renderSidebarPanels();
            clearTimeout(chatSearchTimer);
            chatSearchTimer = setTimeout(async () => {
                try {
                    await loadChats();
                } catch {
                    showToast("Unable to search chats.", "error");
                }
            }, 180);
        });

        newChatButton.addEventListener("click", createNewChat);
        fileUploadButton.addEventListener("click", () => {
            chatFileInput.click();
        });
        chatFileInput.addEventListener("change", () => {
            addPendingFiles(chatFileInput.files);
            chatFileInput.value = "";
        });
        voiceButton.addEventListener("click", toggleVoiceRecording);
        sendButton.addEventListener("click", handleSend);
        composer.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleSend();
            }
        });
        window.addEventListener("beforeunload", () => {
            cleanupVoiceRecorder(voiceRecorder);
        });

        async function boot() {
            applyTheme(getStoredTheme());
            state.voiceSupported = detectVoiceSupport();
            state.sidebarClosed = localStorage.getItem(SIDEBAR_CLOSED_STORAGE_KEY) === "1";
            state.historyMinimized = localStorage.getItem(HISTORY_MINIMIZED_STORAGE_KEY) === "1";
            state.searchPanelOpen = false;
            renderSidebarVisibility();
            renderSidebarPanels();
            renderVoiceButton();
            renderPendingAttachments();
            setVoiceStatus(
                state.voiceSupported
                    ? "Mic ready. Voice transcription stays local on this PC."
                    : "Microphone recording is not supported in this browser.",
                state.voiceSupported ? "idle" : "error"
            );
            if (initialShellPayloadNode?.textContent) {
                try {
                    applyShellPayload(JSON.parse(initialShellPayloadNode.textContent));
                } catch {
                    showToast("Unable to load initial Ollama models.", "error");
                }
            }
            chatSearchInput.value = "";
            state.chatSearchQuery = "";
            await loadChats();
            openDraftChat({ focusComposer: true });
        }

        boot();
