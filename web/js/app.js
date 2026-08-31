
        document.addEventListener('contextmenu', e => e.preventDefault());

        // ==========================================================
        // [보안 패치] Eel 세션 토큰 프록시 (Session Token Proxy)
        // 모든 eel 호출에 세션 토큰을 자동으로 주입합니다.
        // ==========================================================
        (function () {
            const originalEel = window.eel;
            // URL 파라미터에서 토큰 파싱 (로컬 전용)
            const urlParams = new URLSearchParams(window.location.search);
            const urlToken = urlParams.get('token');

            // [수정] localhost(내 PC)인 경우에만 편의를 위해 세션 스토리지를 활용해 새로고침 시에도 토큰을 유지
            const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
            let sessionToken = urlToken || (isLocalhost ? sessionStorage.getItem('eel_session_token') || "" : "");

            // 로컬 호스트일 때만 토큰 저장 (원격 세션은 새로고침 시 만료되도록 저장하지 않음)
            if (urlToken && isLocalhost) {
                sessionStorage.setItem('eel_session_token', urlToken);
                const newUrl = window.location.pathname + window.location.hash;
                window.history.replaceState({}, document.title, newUrl);
            } else if (urlToken) {
                // 원격 접속인데 URL에 토큰이 있는 경우 (보안상 히스토리만 제거)
                const newUrl = window.location.pathname + window.location.hash;
                window.history.replaceState({}, document.title, newUrl);
            }

            // Eel 객체를 위한 프록시 생성
            const eelProxy = new Proxy(originalEel, {
                get(target, prop) {
                    const originalFunc = target[prop];
                    // 중요: 오직 '_py'로 끝나는 사용자 정의 함수에만 토큰을 주입합니다.
                    // Eel의 내부 함수(init, start, heartbeat 등)는 건드리지 않습니다.
                    if (typeof originalFunc === 'function' && prop.endsWith('_py')) {
                        return (...args) => {
                            // 첫 번째 인자로 세션 토큰 주입
                            return originalFunc(sessionToken, ...args);
                        };
                    }
                    return originalFunc;
                },
                set(target, prop, value) {
                    target[prop] = value;
                    return true;
                }
            });

            // 원본 eel 객체를 프록시로 대체
            window.eel = eelProxy;

            // 전역 토큰 설정 함수
            window.setEelSessionToken = function (token) {
                sessionToken = token;
                // 로컬 호스트인 경우에만 새로고침 방지를 위해 토큰 저장
                if (isLocalhost) {
                    sessionStorage.setItem('eel_session_token', token);
                }
            };

            // [보안 패치] 인증 상태 확인용 함수
            window.isEelAuthenticated = function () {
                // 토큰이 존재하고 비어있지 않은지 확인
                return (sessionToken !== null && sessionToken !== "");
            };
        })();

        let currentSelectedServerName = "", currentLang = "ko", currentTranslations = {}, globalPlayerList = [];
        let neneDataInterval = null;

        window.onload = function () {
            initApp();
            startAccessRestrictionPolling(); // [보안 패치] 무단 접근 감시 시작
        };

        function splashStatus(msg) {
            if (eel.splash_status) eel.splash_status(msg);
        }

        async function initApp() {
            splashStatus("설정 불러오는 중...");
            const isFirstRun = await eel.init_system_py()();
            await eel.check_java_status_py()();
            await loadLauncherConfig();
            await checkRemoteLockScreen(); // [추가] 원격 락 스크린 인증 체크 추가
            const config = await eel.get_launcher_config_py()();
            if (config && config.remote_enabled === true) {
                openModal('remoteNoticeModal');
            }
            refreshServerList();
            loadVersionList();

            if (isFirstRun) {
                openModal('welcomeModal');
            }
            eel.mark_web_ready();
        }

        // [보안 패치] 미인증 세션에 대해 0.5초마다 경고 팝업 강제 노출 및 자가복구
        let accessBlockLogged = false;
        function startAccessRestrictionPolling() {
            setInterval(async () => {
                // 원격 제어가 활성화되어 있는데 인증이 안 된 상태라면 (로컬 토큰도 없는 경우)
                const config = await eel.get_launcher_config_py()();
                if (config && config.remote_enabled === true) {
                    // [수정] 백엔드에서 인증 실패를 보냈거나, 브라우저 토큰이 비어있는 경우
                    if (!config.is_authenticated || !window.isEelAuthenticated()) {
                        if (!accessBlockLogged) {
                            accessBlockLogged = true;
                            eel.log_access_blocked_py()();
                        }
                        // 세션 만료 시 데이터 클리어 (락 스크린 노출 유도)
                        sessionToken = "";
                        sessionStorage.removeItem('eel_session_token');

                        let modal = document.getElementById('accessRestrictedModal');

                        // [보안 강화] F12로 엘리먼트를 삭제해도 0.5초만에 다시 생성 (증식/자가복구)
                        if (!modal) {
                            const modalHtml = `
                            <div id="accessRestrictedModal" class="modal-overlay" style="z-index: 19000; background: rgba(0,0,0,0.7); backdrop-filter: blur(3px);">
                                <div class="modal" style="width: 320px; border-color: #ff5252; text-align: center;">
                                    <i class="bi bi-shield-slash" style="font-size: 48px; color: #ff5252; margin-bottom: 15px;"></i>
                                    <h3 style="color: #ff5252; margin-bottom: 10px;">Security Warning</h3>
                                    <p style="color: #eee; font-size: 14px; margin-bottom: 20px; font-weight: 700;">
                                        Access Restricted Session
                                    </p>
                                    <div style="color: #ff5252; font-size: 11px; margin-top: 10px;">Please authenticate via the login screen above.</div>
                                </div>
                            </div>`;
                            document.body.insertAdjacentHTML('beforeend', modalHtml);
                            modal = document.getElementById('accessRestrictedModal');
                        }

                        // 이미 팝업이 떠있으면 추가로 띄우지 않음
                        if (modal && !modal.classList.contains('show')) {
                            openModal('accessRestrictedModal');
                        }
                    }
                }
            }, 500);
        }
        async function tryCloseApp() { const r = await eel.try_close_app_py()(); if (r === "blocked") { showToast(currentTranslations["msg_cannot_close"] || "⚠️ Server is running!", "error"); } else { window.close(); } }
        async function loadLauncherConfig() {
            const c = await eel.get_launcher_config_py()();
            if (c) {
                if (c.language) await changeLanguage(c.language);
                if (c.mirror_url) document.getElementById('mirrorUrlInput').value = c.mirror_url;
                if (c.ui_mode) document.getElementById('uiModeSelect').value = c.ui_mode;
                if (c.theme) {
                    const ts = document.getElementById('themeSelect');
                    if (ts) ts.value = c.theme;
                    applyTheme(c.theme);
                }
                await populateLanguageSelects();

                // [보안 패치] 원격 키가 없으면 상단 경고 배너 표시
                const banner = document.getElementById('remoteSecurityWarningBanner');
                if (c.remote_key_exists === false) {
                    banner.classList.remove('hidden');
                } else {
                    banner.classList.add('hidden');
                }

                // [추가] 원격 활성화 상태일 경우 상단 알림 배너 표시
                const enabledBanner = document.getElementById('remoteEnabledWarningBanner');
                if (c.remote_enabled === true) {
                    enabledBanner.classList.remove('hidden');
                } else {
                    enabledBanner.classList.add('hidden');
                }
            }
        }
        const THEME_CSS = {
            light: 'css/theme-light.css',
            dark: 'css/theme-dark.css'
        };
        function applyTheme(name) {
            const href = THEME_CSS[name];
            let link = document.getElementById('faceliftStyle');
            if (href) {
                if (!link) {
                    link = document.createElement('link');
                    link.id = 'faceliftStyle';
                    link.rel = 'stylesheet';
                    document.head.appendChild(link);
                }
                link.disabled = false;
                link.href = href;
            } else if (link) {
                link.disabled = true;
            }
        }
        async function saveLauncherSettings() {
            const l = document.getElementById('langSelect').value;
            const m = document.getElementById('mirrorUrlInput').value;
            const u = document.getElementById('uiModeSelect').value;
            const t = document.getElementById('themeSelect').value;
            try {
                await Promise.race([
                    eel.save_launcher_config_py({ "language": l, "mirror_url": m, "ui_mode": u, "theme": t })(),
                    new Promise((_, rej) => setTimeout(() => rej(new Error("시간 초과")), 30000))
                ]);
                showToast("Saved", "success");
                closeModal('launcherSettingsModal');
                openModal('restartAppModal');
            } catch (err) {
                showToast("저장 실패: " + (err && err.message ? err.message : err), "error");
                closeModal('launcherSettingsModal');
            }
        }

        function openMirrorPresetModal() { openModal('mirrorPresetModal'); }
        function applyMirrorPreset(url) { document.getElementById('mirrorUrlInput').value = url; closeModal('mirrorPresetModal'); showToast("미러 URL이 변경되었습니다. 저장 버튼을 눌러 적용하세요.", "info"); }
        function showWelcomePage2() {
            const l = document.getElementById('welcomeLangSelect').value;
            const m = document.getElementById('welcomeMirrorUrl').value;
            const u = document.getElementById('welcomeUiMode').value;
            eel.save_launcher_config_py({ "language": l, "mirror_url": m, "ui_mode": u })();
            document.getElementById('welcomePage1').style.display = 'none';
            document.getElementById('welcomePage2').style.display = 'block';
        }
        async function saveFirstRunSettings() {
            closeModal('welcomeModal');
            await loadLauncherConfig();
        }
        async function populateLanguageSelects() {
            const langs = await eel.get_available_languages_py()();
            ['langSelect', 'welcomeLangSelect'].forEach(id => {
                const sel = document.getElementById(id);
                if (!sel) return;
                sel.innerHTML = '';
                langs.forEach(l => {
                    const opt = document.createElement('option');
                    opt.value = l.code;
                    opt.textContent = l.name;
                    sel.appendChild(opt);
                });
                sel.value = currentLang;
            });
        }
        async function changeLanguage(c) { currentLang = c; currentTranslations = await eel.get_translation_py(c)(); if (!currentTranslations) return; document.querySelectorAll('[data-i18n]').forEach(e => { const k = e.getAttribute('data-i18n'); if (currentTranslations[k]) { if (e.tagName === 'INPUT' || e.tagName === 'TEXTAREA') e.placeholder = currentTranslations[k]; else e.innerHTML = currentTranslations[k]; } }); }
        async function loadVersionList() { const s = document.getElementById('newServerVersion'); const v = await eel.get_papermc_versions_py()(); if (v && v.length > 0) { s.innerHTML = ""; v.forEach(i => s.innerHTML += `<option value="${i}">${i}</option>`); } else { s.innerHTML = `<option value="1.21.1">1.21.1</option><option value="1.20.4">1.20.4</option>`; } }
        async function refreshServerList() { let s = await eel.get_server_list_py()(); let l = document.getElementById('sidebarList'); l.innerHTML = ""; s.forEach(i => { const a = (i.name === currentSelectedServerName) ? "active" : ""; l.innerHTML += `<div class="server-item ${a}" onclick="selectServer('${i.name}', this)"><h4>${i.name}</h4><p><span style="color:${i.status === 'Running' ? 'var(--accent-green)' : 'var(--text-sub)'}">${i.status}</span><span style="color:var(--text-sub); margin-left:8px; font-size:11px;">${i.version}</span></p></div>`; }); }
        async function selectServer(n, e) { currentSelectedServerName = n; document.getElementById('logs').innerHTML = ""; document.getElementById('emptyScreen').style.display = 'none'; document.getElementById('mainContent').classList.add('active'); document.querySelectorAll('.server-item').forEach(i => i.classList.remove('active')); if (e) e.classList.add('active'); document.getElementById('headerTitle').innerText = n; await eel.select_server_py(n)(); loadSettings(); const dbTab = document.querySelector('.tab[onclick*="dashboard"]'); if (dbTab) switchTab('dashboard', dbTab); if (window.innerWidth <= 850) closeSidebar(); }
        function toggleSidebar() { document.querySelector('.sidebar').classList.toggle('show'); document.querySelector('.sidebar-overlay').classList.toggle('show'); }
        function closeSidebar() { document.querySelector('.sidebar').classList.remove('show'); document.querySelector('.sidebar-overlay').classList.remove('show'); }

        async function createNewServer() {
            let n = document.getElementById('newServerName').value.trim();
            let v = document.getElementById('newServerVersion').value;
            let m = document.getElementById('mirrorUrlInput').value;
            let j = document.getElementById('newServerJava').value;

            // 추가 설정값 수집
            let diff = document.getElementById('newServerDifficulty').value;
            let gm = document.getElementById('newServerGamemode').value;
            let ram = parseInt(document.getElementById('newServerRam').value);
            let world = document.getElementById('newServerImportWorld').value;

            let b = document.getElementById('btnCreateReal');
            if (!n) return showToast("Name required", "error");

            // 버튼 비활성화 및 상태 표시
            b.disabled = true;
            b.style.cursor = "not-allowed";
            b.innerText = "Creating...";

            let r = "";
            try {
                // 백엔드 호출 (타임아웃 180s — 연결 불가 시 침묵적 멈춤 방지)
                r = await Promise.race([
                    eel.create_new_server_real_py(n, v, m, j, diff, gm, ram, world)(),
                    new Promise((_, rej) => setTimeout(() => rej(new Error("요청 시간 초과(다운로드 연결 확인)")), 180000))
                ]);
            } catch (err) {
                r = " Error: " + (err && err.message ? err.message : err);
            } finally {
                b.disabled = false;
                b.style.cursor = "pointer";
                b.innerText = currentTranslations["btn_create"] || "Create Server";
                changeLanguage(currentLang);
                closeModal('newServerModal');
            }

            if (r && r.includes("✅")) {
                showToast("Success", "success");
                refreshServerList();
            } else showToast(r || "실패", "error");
        }

        async function browseLocalWorldFolder() {
            const path = await eel.select_local_world_folder_py()();
            if (path) {
                const select = document.getElementById('newServerImportWorld');
                const oldCustom = document.getElementById('customWorldPathOption');
                if (oldCustom) oldCustom.remove();

                const option = document.createElement('option');
                option.id = 'customWorldPathOption';
                option.value = path;
                const folderName = path.split(/[\\/]/).pop();
                option.innerText = `📂 [Explorer] ${folderName}`;
                option.selected = true;
                select.prepend(option);
            }
        }

        async function prepareNewServerModal() {
            openModal('newServerModal');
            const javaSelect = document.getElementById('newServerJava');
            const worldSelect = document.getElementById('newServerImportWorld');

            // 저장된 URL에서 버전 목록 다시 불러오기
            document.getElementById('newServerVersion').innerHTML = "<option>Loading...</option>";
            await loadVersionList();

            javaSelect.innerHTML = "<option>Scanning...</option>";
            worldSelect.innerHTML = "<option value=''>Scanning...</option>";

            // 자바 버전 스캔
            const javaList = await eel.scan_java_versions_py()();
            javaSelect.innerHTML = "";
            javaList.forEach(java => {
                const option = document.createElement('option');
                option.value = java.path;
                let label = `Java ${java.version}`;
                if (java.is_current) label += " (Default)";
                option.innerText = label;
                javaSelect.appendChild(option);
            });

            // 싱글플레이 월드 목록 스캔
            const worldList = await eel.get_singleplayer_worlds_py()();
            worldSelect.innerHTML = `<option value="" data-i18n="modal_new_import_hint">${currentTranslations["modal_new_import_hint"] || "(Select None)"}</option>`;
            worldList.forEach(w => {
                const option = document.createElement('option');
                option.value = w;
                option.innerText = w;
                worldSelect.appendChild(option);
            });
        }

        let serverToDelete = "";
        function askDeleteServer() { let n = document.getElementById('headerTitle').innerText; serverToDelete = n; document.getElementById('delTargetName').innerText = n; openModal('deleteConfirmModal'); }
        async function confirmDeleteProcess() {
            closeModal('deleteConfirmModal');
            // [수정] 보안 프록시 적용을 위해 _py 접미사 추가
            let r = await eel.delete_server_real_py(serverToDelete)();
            if (r.includes("✅")) {
                showToast("Deleted", "success");
                document.getElementById('emptyScreen').style.display = 'flex';
                document.getElementById('mainContent').classList.remove('active');
                refreshServerList();
            } else {
                showToast(r, "error");
            }
        }
        // [추가] 백엔드에서 호출하는 진행률 업데이트 함수
        eel.expose(update_download_progress_js);
        function update_download_progress_js(msg) {
            const statusEl = document.getElementById('importStatusText');
            const barEl = document.getElementById('importProgressBar');
            if (statusEl) statusEl.innerText = msg;

            // "Copying (45%)..." 에서 숫자 추출
            const match = msg.match(/(\d+)%/);
            if (match && barEl) {
                barEl.style.width = match[1] + "%";
            }
        }

        async function processServerImport() {
            const btn = document.getElementById('btnImportServer');
            if (!btn || btn.disabled) return;

            // UI 초기화
            const statusArea = document.getElementById('importProgressArea');
            const statusText = document.getElementById('importStatusText');
            const progressBar = document.getElementById('importProgressBar');

            if (statusArea) statusArea.classList.remove('hidden');
            if (statusText) statusText.innerText = currentTranslations["status_import_preparing"] || "복사 준비 중...";
            if (progressBar) progressBar.style.width = "0%";

            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.querySelector('span').innerText = currentTranslations["status_import_copying"] || "복사 중...";

            const r = await eel.import_existing_server_py()();

            btn.disabled = false;
            btn.style.opacity = '1';
            btn.querySelector('span').innerText = currentTranslations["btn_import_server"] || "외부 서버 불러오기";
            if (statusArea) statusArea.classList.add('hidden');

            if (r.includes('✅')) {
                showToast(currentTranslations["msg_import_done"] || "불러오기 완료!", "success");
                closeModal('serverCreateTypeModal');
                refreshServerList();
            } else if (r.includes('⚠️')) {
                // 취소 시에도 UI 정리
                showToast(r, "info");
            } else {
                showToast(r, "error");
            }
        }
        async function askUpdateServerCore() {
            const sel = document.getElementById('updateCoreVersion');
            if (!sel) return showToast("버전 목록을 불러오는 중입니다...", "error");
            const v = sel.value;
            if (!v) {
                const opt = sel.options[0].text;
                if (opt.includes('Loading')) return showToast("버전 목록 로딩 중... 잠시 후 다시 시도하세요", "error");
                if (opt.includes('Failed')) return showToast("버전 목록을 불러오지 못했습니다. 미러 URL을 확인하세요", "error");
                return showToast("버전을 선택하세요", "error");
            }
            const serverName = document.getElementById('headerTitle').innerText;
            if (!serverName) return showToast("서버를 선택하세요", "error");
            const msgEl = document.getElementById('updateCoreConfirmMsg');
            if (msgEl) msgEl.innerText = `서버 "${serverName}"를 ${v}(으)로 업데이트하시겠습니까?`;
            openModal('updateCoreConfirmModal');
        }
        async function executeUpdateServerCore() {
            closeModal('updateCoreConfirmModal');
            const v = document.getElementById('updateCoreVersion').value;
            const mirrorInput = document.getElementById('mirrorUrlInput');
            const m = mirrorInput ? mirrorInput.value : '';
            const statusEl = document.getElementById('updateCoreStatus');
            const btn = document.querySelector('[onclick="askUpdateServerCore()"]');

            if (btn) { btn.disabled = true; btn.style.opacity = '0.5'; }
            statusEl.style.display = 'block';
            statusEl.style.color = 'var(--accent-blue)';
            statusEl.innerText = '⏳ 다운로드 중...';

            let r = "";
            try {
                r = await Promise.race([
                    eel.update_server_core_py(v, m)(),
                    new Promise((_, rej) => setTimeout(() => rej(new Error("요청 시간 초과(다운로드 연결 확인)")), 180000))
                ]);
            } catch (err) {
                r = " Error: " + (err && err.message ? err.message : err);
            } finally {
                if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
            }

            if (r && r.includes('✅')) {
                statusEl.style.color = 'var(--accent-green)';
                statusEl.innerText = r;
                showToast("버전 변경 완료!", "success");
                refreshServerList();
            } else {
                statusEl.style.color = 'var(--accent-red)';
                statusEl.innerText = r || '❌ 실패';
                showToast(r || "실패", "error");
            }
        }
        async function selectLocalCoreFile() {
            const statusEl = document.getElementById('updateCoreStatus');
            statusEl.style.display = 'block';
            statusEl.style.color = 'var(--accent-blue)';
            statusEl.innerText = '⏳ 파일 선택 대기 중...';

            const r = await eel.select_local_core_py()();

            if (r && r.includes('✅')) {
                statusEl.style.color = 'var(--accent-green)';
                statusEl.innerText = r;
                showToast("코어 등록 완료!", "success");
                refreshServerList();
            } else if (r.includes('⚠️')) {
                statusEl.style.display = 'none';
            } else {
                statusEl.style.color = 'var(--accent-red)';
                statusEl.innerText = r || '❌ 실패';
                showToast(r || "실패", "error");
            }
        }
        const checkboxSettings = ['allow-flight', 'allow-nether', 'broadcast-console-to-ops', 'broadcast-rcon-to-ops', 'debug', 'enable-command-block', 'enable-jmx-monitoring', 'enable-query', 'enable-rcon', 'enable-status', 'enforce-secure-profile', 'enforce-whitelist', 'force-gamemode', 'generate-structures', 'hardcore', 'hide-online-players', 'log-ips', 'online-mode', 'prevent-proxy-connections', 'pvp', 'require-resource-pack', 'spawn-animals', 'spawn-monsters', 'spawn-npcs', 'sync-chunk-writes', 'use-native-transport', 'white-list', 'accepts-transfers', 'auto_backup'];
        const textSettings = ['java_path', 'motd', 'max-players', 'server-port', 'server-ip', 'view-distance', 'simulation-distance', 'max-tick-time', 'network-compression-threshold', 'rate-limit', 'max-world-size', 'level-name', 'level-seed', 'level-type', 'generator-settings', 'gamemode', 'difficulty', 'spawn-protection', 'player-idle-timeout', 'op-permission-level', 'resource-pack', 'rcon.port', 'rcon.password', 'query.port', 'entity-broadcast-range-percentage', 'max-chained-neighbor-updates', 'region-file-compression', 'bug-report-link', 'initial-enabled-packs', 'initial-disabled-packs', 'backup_interval'];

        async function loadSettings() {
            let p = await eel.load_properties_py()();
            if (!p) return;

            // [추가] RAM 할당량 UI 동기화
            if (p['ram_allocation']) {
                const rs = document.getElementById('ramSlider');
                if (rs) {
                    rs.value = p['ram_allocation'];
                    updateRamLabel(p['ram_allocation']);
                }
            }

            checkboxSettings.forEach(i => {
                const e = document.getElementById(i);
                if (e) e.checked = (p[i] === 'true' || p[i] === true);
            });

            textSettings.forEach(i => {
                const e = document.getElementById(i);
                if (e && p[i]) e.value = String(p[i]).replace(/\\:/g, ":");
            });

            const j = document.getElementById('java_path');
            if (p['java_path']) {
                j.value = p['java_path'];
            } else {
                j.value = "java";
            }
        }

        async function saveSettings() {
            let d = {};
            checkboxSettings.forEach(i => { const e = document.getElementById(i); if (e) d[i] = e.checked; });
            textSettings.forEach(i => { const e = document.getElementById(i); if (e) d[i] = e.value; });

            // [추가] RAM 할당량 값 포함
            const ramVal = document.getElementById('ramSlider').value;
            d['ram_allocation'] = parseInt(ramVal);

            let ok = true;
            try {
                await Promise.race([
                    eel.save_properties_py(d)(),
                    new Promise((_, rej) => setTimeout(() => rej(new Error("시간 초과")), 30000))
                ]);
                // [추가] 별도의 RAM 저장 API 호출 (nene_config.json 보존용)
                if (eel.save_ram_allocation_py) {
                    try { await eel.save_ram_allocation_py(parseInt(ramVal))(); } catch (e) {}
                }
            } catch (err) {
                ok = false;
                showToast("저장 실패: " + (err && err.message ? err.message : err), "error");
            }
            if (ok) showToast("Saved", "success");
            loadSettings();
            showToast("🔄 서버 목록 리로딩 중...", "info");
            await refreshServerList();
            loadVersionList();
        }
        async function saveJavaRamSettings() {
            let d = {};
            d['ram_allocation'] = parseInt(document.getElementById('ramSlider').value);
            d['java_path'] = document.getElementById('java_path').value;
            try {
                await Promise.race([
                    eel.save_properties_py(d)(),
                    new Promise((_, rej) => setTimeout(() => rej(new Error("시간 초과")), 30000))
                ]);
                showToast("Java settings saved", "success");
            } catch (err) {
                showToast("저장 실패: " + (err && err.message ? err.message : err), "error");
            }
            closeModal('javaSettingsModal');
        }
        function openModal(id) { document.getElementById(id).style.display = 'flex'; setTimeout(() => document.getElementById(id).classList.add('show'), 10); }
        function closeModal(id) { document.getElementById(id).classList.remove('show'); setTimeout(() => document.getElementById(id).style.display = 'none', 300); }
        function updateRamLabel(v) { 
            const d = document.getElementById('ramDisplay'); 
            if (d) d.textContent = v; 
            const c = document.getElementById('ramCardDisplay');
            if (c) c.textContent = v + ' GB';
        }

        async function startServer() {
            let ram = document.getElementById('ramSlider').value;
            document.getElementById('btnStart').classList.add('hidden');
            document.getElementById('btnStop').classList.remove('hidden');
            document.getElementById('btnRestart').classList.remove('hidden');
            document.getElementById('statusText').innerText = "LOADING...";
            showToast("Starting...", "info");

            if (eel.get_public_ip_py) {
                document.getElementById('publicIp').innerText = "Checking...";
                let ip = await eel.get_public_ip_py()();
                document.getElementById('publicIp').innerText = ip;
            }

            // 시작 전 설정을 확실히 전용 파일에 저장하여 꼬임 방지 (백엔드 자동보정 도입으로 제거)
            // await saveSettings();

            let r = await eel.start_server_py(ram)();

            if (r.includes("❌") || r.includes("⚠️")) { showToast(r, "error"); update_status_js(false); }
            else setTimeout(refreshServerList, 1000);
        }

        function switchTab(id, btn) {
            document.querySelectorAll('.content').forEach(e => e.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(e => e.classList.remove('active'));
            document.getElementById(id).classList.add('active'); btn.classList.add('active');
            if (id === 'settings') loadSettings();
            if (id === 'plugins') refreshPluginList();
            if (id === 'info') loadServerInfo();
            if (id === 'danger') loadDangerVersions();
        }

        async function loadDangerVersions() {
            const select = document.getElementById('updateCoreVersion');
            if (!select) return;
            select.innerHTML = '<option value="">Loading versions...</option>';
            const versions = await eel.get_papermc_versions_py()();
            if (versions && versions.length > 0) {
                select.innerHTML = "";
                versions.forEach(v => {
                    select.innerHTML += `<option value="${v}">${v}</option>`;
                });
            } else {
                select.innerHTML = '<option value="">Failed to load</option>';
            }
        }


        function sendCommand(c) { eel.send_command_py(c); }
        document.getElementById('cmdInput').addEventListener('keypress', (e) => { if (e.key === 'Enter' && e.target.value.trim() !== "") { sendCommand(e.target.value); e.target.value = ""; } });
        async function triggerBackup() { if (!currentSelectedServerName) return; await eel.trigger_backup_py(currentSelectedServerName)(); showToast("Backup Started", "info"); }
        eel.expose(update_player_list_js);
        function update_player_list_js(playerDataList) {
            globalPlayerList = playerDataList.map(p => p.name);
            const l = document.getElementById('playerList');
            l.innerHTML = "";

            const onlinePlayers = playerDataList.filter(p => p.online);
            const offlinePlayers = playerDataList.filter(p => !p.online);

            if (document.getElementById('playerCount')) {
                document.getElementById('playerCount').innerText = onlinePlayers.length;
            }

            if (playerDataList.length === 0) {
                l.innerHTML = `<div class="empty-msg" style="text-align:center;color:#666;width: 100%;padding: 20px 0;">${currentTranslations["msg_no_players"] || "No players."}</div>`;
                return;
            }

            onlinePlayers.forEach(p => {
                const avatarUrl = `https://minotar.net/avatar/${p.name}/40.png`;
                l.innerHTML += `
                    <div class="player-card" onclick="openPlayerDetail('${p.name}', true)">
                        <div class="p-info">
                            <div class="avatar" style="background-image: url('${avatarUrl}');"></div>
                            <div style="font-weight:700;">${p.name}</div>
                        </div>
                        <div style="font-size:12px; color:var(--accent-green); font-weight:700;">● Online</div>
                    </div>`;
            });

            if (offlinePlayers.length > 0) {
                if (onlinePlayers.length > 0) {
                    l.innerHTML += `<div style="grid-column: 1 / -1; margin-top:15px; padding-bottom:5px; border-bottom:1px solid var(--border-color); color:var(--text-sub); font-size:12px; font-weight:700;">Offline Players</div>`;
                }
                offlinePlayers.forEach(p => {
                    const avatarUrl = `https://minotar.net/avatar/${p.name}/40.png`;
                    l.innerHTML += `
                        <div class="player-card" onclick="openPlayerDetail('${p.name}', false)" style="opacity: 0.55; border-style: dashed;">
                            <div class="p-info">
                                <div class="avatar" style="background-image: url('${avatarUrl}'); filter: grayscale(100%);"></div>
                                <div style="font-weight:700; color:#aaa;">${p.name}</div>
                            </div>
                            <div style="font-size:12px; color:#666;">○ Offline</div>
                        </div>`;
                });
            }
        }

        let currentDetailPlayer = "";

        async function openPlayerDetail(n, isOnline) {
            currentDetailPlayer = n;
            document.getElementById('pDetailName').innerText = n;
            document.getElementById('pDetailJoin').innerText = "...";
            document.getElementById('pDetailUUID').innerText = "...";

            const statusEl = document.getElementById('pDetailStatus');
            if (isOnline) {
                statusEl.innerText = "Online";
                statusEl.style.color = "var(--accent-green)";
            } else {
                statusEl.innerText = "Offline";
                statusEl.style.color = "#888";
            }

            const skinView = document.querySelector('.player-detail-modal .skin-view');
            skinView.innerHTML = `<img src="https://minotar.net/armor/body/${n}/150.png" style="height:180px; width:auto; image-rendering: pixelated; ${!isOnline ? 'filter: grayscale(100%); opacity:0.6;' : ''}">`;

            openModal('playerDetailModal');

            const paperVersions = await eel.get_papermc_versions_py()();
            const i = await eel.get_player_detail_py(n)();
            if (i) {
                document.getElementById('pDetailJoin').innerText = i.join_time;
                document.getElementById('pDetailUUID').innerText = "UUID: " + i.uuid;
            }
        }

        async function openNeneDataModal() {
            closeModal('playerDetailModal');

            const n = currentDetailPlayer;
            document.getElementById('neneDetailName').innerText = n;
            document.getElementById('neneDataContent').innerText = "Loading data...";

            const skinView = document.querySelector('#neneDataModal .skin-view');
            skinView.innerHTML = `<img src="https://minotar.net/armor/body/${n}/150.png" style="height:180px; width:auto; image-rendering: pixelated;">`;

            openModal('neneDataModal');

            await refreshNeneDataUI();

            if (neneDataInterval) clearInterval(neneDataInterval);
            neneDataInterval = setInterval(refreshNeneDataUI, 3000);
        }

        async function refreshNeneDataUI() {
            const n = currentDetailPlayer;
            const modal = document.getElementById('neneDataModal');
            if (modal.style.display === 'none') {
                if (neneDataInterval) clearInterval(neneDataInterval);
                return;
            }

            const data = await eel.get_nene_player_data_py(n)();
            const contentBox = document.getElementById('neneDataContent');

            if (!contentBox) return;

            if (data) {
                let html = "";

                if (data.nickname) {
                    html += `<div class="p-stat-row"><span class="p-stat-label">이름</span><span class="p-stat-val" style="color:var(--accent-blue);">${data.nickname}</span></div>`;
                }

                for (const [key, value] of Object.entries(data)) {
                    if (key === 'nickname') continue;

                    let displayValue = "";

                    if (typeof value === 'object' && value !== null) {
                        for (const [subKey, subValue] of Object.entries(value)) {
                            displayValue += `<div class="nested-stat"><span class="nested-key">${subKey}:</span> <span class="nested-val">${subValue}</span></div>`;
                        }
                    } else {
                        displayValue = value;
                    }

                    const displayKey = key.charAt(0).toUpperCase() + key.slice(1);

                    html += `<div class="p-stat-row"><span class="p-stat-label">${displayKey}</span><span class="p-stat-val" style="font-size:13px;">${displayValue}</span></div>`;
                }

                contentBox.innerHTML = html;
            } else {
                contentBox.innerHTML = "<div style='text-align:center; color:#666; padding:20px;'>데이터를 찾을 수 없습니다.<br>(Data Not Found)</div>";
            }
        }

        function closeNeneDataModal() {
            if (neneDataInterval) clearInterval(neneDataInterval);
            closeModal('neneDataModal');
        }

        let pendingAction = null; let pendingTarget = "";
        function askAction(a, d) { pendingAction = a; pendingTarget = currentDetailPlayer; document.getElementById('actionConfirmText').innerHTML = `${currentTranslations.modal_del_msg} <b style="color:white">${pendingTarget}</b><br>Action: <b>${d}</b>`; openModal('actionConfirmModal'); }
        async function confirmAction() { closeModal('actionConfirmModal'); if (!pendingAction || !pendingTarget) return; let c = ""; if (pendingAction === 'op') c = `op ${pendingTarget}`; else if (pendingAction === 'deop') c = `deop ${pendingTarget}`; else if (pendingAction === 'kick') c = `kick ${pendingTarget} Kicked`; else if (pendingAction === 'ban') c = `ban ${pendingTarget} Banned`; if (c) { await eel.send_command_py(c)(); showToast("Command Sent", "success"); if (pendingAction === 'kick' || pendingAction === 'ban') closeModal('playerDetailModal'); } pendingAction = null; }
        let currentListType = "";
        async function openListManager(t) { currentListType = t; const tr = currentTranslations; if (t === 'whitelist') document.getElementById('listTitle').innerText = tr.btn_whitelist; else if (t === 'banlist') document.getElementById('listTitle').innerText = tr.btn_banlist; else document.getElementById('listTitle').innerText = "IP 차단 관리"; document.getElementById('listInput').value = ""; openModal('listManagerModal'); await refreshListManager(); }
        async function refreshListManager() { const c = document.getElementById('listContainer'); c.innerHTML = "..."; const l = await eel.get_manage_list_py(currentListType)(); c.innerHTML = ""; if (l.length === 0) { c.innerHTML = "<div style='color:#666; text-align:center; padding:20px;'>Empty</div>"; return; } const tr = currentTranslations; const b = tr.btn_delete || "Delete"; l.forEach(n => { let ct = 'remove'; if (currentListType === 'banlist') ct = 'pardon'; else if (currentListType === 'ip-banlist') ct = 'pardon-ip'; const d = document.createElement('div'); d.className = 'list-item'; d.innerHTML = `<span>${n}</span> <button class="list-btn-s" onclick="modifyList('${ct}', '${n}')">${b}</button>`; c.appendChild(d); }); }
        async function addItemToList() { const n = document.getElementById('listInput').value; if (!n) return; let c = ""; if (currentListType === 'whitelist') c = `whitelist add ${n}`; else if (currentListType === 'banlist') c = `ban ${n}`; else if (currentListType === 'ip-banlist') c = `ban-ip ${n}`; eel.send_command_py(c); document.getElementById('listInput').value = ""; showToast("Added", "info"); setTimeout(refreshListManager, 1000); }
        async function modifyList(a, n) { let c = ""; if (a === 'remove') c = `whitelist remove ${n}`; else if (a === 'pardon') c = `pardon ${n}`; else if (a === 'pardon-ip') c = `pardon-ip ${n}`; eel.send_command_py(c); showToast("Removed", "info"); setTimeout(refreshListManager, 1000); }
        eel.expose(update_status_js);
        function update_status_js(isOn) {
            if (isOn) {
                document.getElementById('statusText').innerText = "ONLINE"; document.getElementById('statusSimple').innerText = "Running"; document.getElementById('statusSimple').style.color = "#00e676";
                document.getElementById('btnStart').classList.add('hidden'); document.getElementById('btnStop').classList.remove('hidden'); document.getElementById('btnRestart').classList.remove('hidden');
                if (eel.get_public_ip_py) eel.get_public_ip_py()().then(ip => document.getElementById('publicIp').innerText = ip);
            } else {
                document.getElementById('statusText').innerText = "OFFLINE"; document.getElementById('statusSimple').innerText = "Stopped"; document.getElementById('statusSimple').style.color = "#ff5252";
                document.getElementById('btnStart').classList.remove('hidden'); document.getElementById('btnStop').classList.add('hidden'); document.getElementById('btnRestart').classList.add('hidden');
            }
            refreshServerList();
        }
        eel.expose(add_log_js);
        function add_log_js(m) { const l = document.getElementById('logs'); l.innerHTML += `<div>${m}</div>`; l.scrollTop = l.scrollHeight; }
        eel.expose(restore_logs_js);
        function restore_logs_js(arr) { const l = document.getElementById('logs'); l.innerHTML = ""; arr.forEach(m => l.innerHTML += `<div>${m}</div>`); l.scrollTop = l.scrollHeight; }
        eel.expose(showToast);
        function showToast(m, t = 'info') { const c = document.getElementById('toast-container'); const e = document.createElement('div'); e.className = `toast ${t}`; e.innerText = m; c.appendChild(e); setTimeout(() => e.remove(), 3000); }
        eel.expose(update_cpu_usage_js);
        function update_cpu_usage_js(p) { const e = document.getElementById('sysCpu'); if (e) e.innerText = p + "%"; }
        eel.expose(update_download_progress_js);
        // [수정] 진행률 표시 로직 개선 및 백엔드 노출
        eel.expose(update_download_progress_js);
        function update_download_progress_js(t) {
            const b = document.getElementById('btnCreateReal');
            if (b) {
                b.disabled = true;
                b.style.cursor = "not-allowed";
                b.innerText = t;
            }
        }
        eel.expose(remote_refresh_js);
        function remote_refresh_js() {
            location.reload();
        }
        eel.expose(update_restore_progress_js);
        function update_restore_progress_js(percent, currentFile) {
            const area = document.getElementById('restoreProgressArea');
            const bar = document.getElementById('restoreProgressBar');
            const text = document.getElementById('restoreProgressText');
            const fileLabel = document.getElementById('restoreCurrentFile');
            if (area) area.classList.remove('hidden');
            if (bar) bar.style.width = percent + '%';
            if (text) text.innerText = percent + '%';
            if (fileLabel) fileLabel.innerText = currentFile || '-';
        }
        function openBackupRestoreModal() {
            if (!currentSelectedServerName) return showToast("서버를 선택하세요", "error");
            openModal('backupRestoreModal');
            loadBackupList();
        }
        async function loadBackupList() {
            if (!currentSelectedServerName) return showToast("서버를 선택하세요", "error");
            const container = document.getElementById('backupListContainer');
            container.innerHTML = '<div style="text-align:center; padding:20px; color:#666; font-size:12px;">' + (currentTranslations["status_loading"] || "Loading...") + '</div>';
            const list = await eel.list_backups_py(currentSelectedServerName)();
            container.innerHTML = '';
            if (!list || list.length === 0) {
                container.innerHTML = '<div style="text-align:center; padding:20px; color:#666; font-size:12px;">' + (currentTranslations["msg_no_backups"] || "백업이 없습니다") + '</div>';
                return;
            }
            list.forEach(b => {
                const div = document.createElement('div');
                div.style.cssText = 'display:flex; justify-content:space-between; align-items:center; padding:6px 8px; border-bottom:1px solid rgba(255,255,255,0.04); cursor:pointer; border-radius:4px;';
                const restoreLabel = currentTranslations["btn_restore"] || "복구";
                div.innerHTML = `<div style="flex:1; min-width:0;"><div style="font-size:12px; color:#ccc; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${b.filename}</div><div style="font-size:10px; color:#888;">${b.date} · ${b.size_mb}MB</div></div><button class="btn" style="padding:4px 8px; font-size:11px; background:rgba(255,152,0,0.1); border:1px solid rgba(255,152,0,0.3); color:var(--accent-orange); flex-shrink:0;" onclick="restoreBackup('${b.filename}')">${restoreLabel}</button>`;
                container.appendChild(div);
            });
        }
        let pendingRestoreFile = "";
        function restoreBackup(filename) {
            if (!currentSelectedServerName) return;
            pendingRestoreFile = filename;
            const msg = (currentTranslations["msg_restore_confirm"] || "정말 복구하시겠습니까? 현재 서버 파일은 모두 삭제됩니다.").replace("{filename}", filename);
            document.getElementById('restoreConfirmMsg').innerText = msg;
            openModal('restoreConfirmModal');
        }
        async function executeRestoreBackup() {
            closeModal('restoreConfirmModal');
            if (!pendingRestoreFile) return;
            const area = document.getElementById('restoreProgressArea');
            area.classList.remove('hidden');
            document.getElementById('restoreProgressBar').style.width = '0%';
            document.getElementById('restoreProgressText').innerText = '0%';
            document.getElementById('restoreCurrentFile').innerText = currentTranslations["status_starting"] || "Starting...";
            await eel.restore_backup_py(currentSelectedServerName, pendingRestoreFile)();
        }
        function sendWhisperReal() { let m = document.getElementById('whisperInput').value; if (!m) return showToast("내용 입력", "error"); eel.send_command_py(`tell ${currentDetailPlayer} ${m}`); showToast("전송 완료", "success"); closeModal('whisperModal'); }
        function openWhisperModal() { document.getElementById('whisperTarget').innerText = currentDetailPlayer; document.getElementById('whisperInput').value = ''; openModal('whisperModal'); }
        function sendBroadcast(t) { let m = "", c = ""; if (t === 'title') { m = document.getElementById('bcTitleInput').value; c = `title @a title "${m}"`; } else if (t === 'subtitle') { m = document.getElementById('bcSubtitleInput').value; c = `title @a subtitle "${m}"`; } else if (t === 'actionbar') { m = document.getElementById('bcActionbarInput').value; c = `title @a actionbar "${m}"`; } else if (t === 'title_clear') { c = `title @a clear`; document.getElementById('bcTitleInput').value = ""; } if (c) eel.send_command_py(c); showToast("전송/설정 완료", "success"); }
        async function openFolder(t) { if (!currentSelectedServerName) return; await eel.open_folder_py(currentSelectedServerName, t)(); showToast("폴더 열림", "success"); }
        function openTpModal() { const t = globalPlayerList.filter(p => p !== currentDetailPlayer); const c = document.getElementById('tpList'); c.innerHTML = ""; if (t.length === 0) { c.innerHTML = "<div style='text-align:center; color:#666; padding: 10px 0;'>선택 가능한 플레이어가 없습니다.</div>"; } else { t.forEach(n => { c.innerHTML += `<div class="list-item"><span>${n}</span> <button class="list-btn-s" onclick="teleportTo('${n}')">이동</button></div>`; }); } openModal('tpModal'); }
        function teleportTo(t) { eel.send_command_py(`tp ${currentDetailPlayer} ${t}`); showToast("이동함", "success"); closeModal('tpModal'); }
        function openBanOptionModal() { closeModal('playerDetailModal'); openModal('banOptionModal'); }
        async function executeBan(t) { let c = ""; const tg = currentDetailPlayer; if (t === 'name') c = `ban ${tg} Banned`; else if (t === 'ip') c = `ban-ip ${tg} IP Banned`; else if (t === 'both') { await eel.send_command_py(`ban ${tg}`)(); await eel.send_command_py(`ban-ip ${tg}`)(); closeModal('banOptionModal'); showToast("Banned", "success"); return; } if (c) { eel.send_command_py(c); showToast("Banned", "success"); } closeModal('banOptionModal'); }
        function openGamemodeModal() { document.getElementById('gmTarget').innerText = currentDetailPlayer; openModal('gamemodeModal'); }
        function executeGamemode(m) { eel.send_command_py(`gamemode ${m} ${currentDetailPlayer}`); closeModal('gamemodeModal'); }
        function cleanServerNameInput(i) { i.value = i.value.replace(/[<>:"/\\|?*]/g, ''); }
        function askStop() { openModal('stopConfirmModal'); }
        function executeStop() { sendCommand('stop'); closeModal('stopConfirmModal'); }
        function askRestart() { openModal('restartConfirmModal'); }
        function executeRestart() { sendCommand('stop'); showToast("Restarting...", "info"); closeModal('restartConfirmModal'); setTimeout(() => startServer(), 5000); }

        async function refreshPluginList() {
            const container = document.getElementById('pluginList');
            container.innerHTML = "...";
            const list = await eel.get_plugin_list_py()();
            container.innerHTML = "";

            if (list.length === 0) {
                container.innerHTML = "<div style='text-align:center; color:#666; padding:20px;'>No plugins found.</div>";
                return;
            }

            list.forEach(p => {
                const div = document.createElement('div');
                div.className = 'plugin-item';

                const infoArea = document.createElement('div');
                infoArea.className = 'plugin-info-area';
                infoArea.onclick = () => openPluginDetail(p.filename);
                infoArea.innerHTML = `<i class="bi bi-plug" style="color:var(--accent-orange); font-size:22px;"></i> <span>${p.name}</span>`;

                const switchLabel = document.createElement('label');
                switchLabel.className = 'switch';
                const input = document.createElement('input');
                input.type = 'checkbox';
                input.checked = p.enabled;
                input.onchange = () => togglePlugin(p.filename, input.checked);

                const slider = document.createElement('span');
                slider.className = 'slider';

                switchLabel.appendChild(input);
                switchLabel.appendChild(slider);

                div.appendChild(infoArea);
                div.appendChild(switchLabel);
                container.appendChild(div);
            });
        }

        async function togglePlugin(filename, isChecked) {
            const res = await eel.toggle_plugin_py(filename, isChecked)();
            if (res.includes("✅")) {
                showToast(res, "success");
                refreshPluginList();
            } else {
                showToast(res, "error");
                refreshPluginList();
            }
        }

        let currentPluginFile = "";
        function openPluginDetail(filename) {
            currentPluginFile = filename;
            document.getElementById('plDetailName').innerText = filename;
            openModal('pluginDetailModal');
        }

        async function confirmDeletePlugin() {
            closeModal('pluginDetailModal');
            const res = await eel.delete_plugin_py(currentPluginFile)();
            if (res.includes("✅")) {
                showToast("Plugin Deleted", "success");
                refreshPluginList();
            } else {
                showToast(res, "error");
            }
        }

        async function loadServerInfo() {
            const info = await eel.get_server_extended_info_py()();
            if (info) {
                document.getElementById('infoCreated').innerText = info.created_at;
                document.getElementById('infoSource').innerText = info.source_url;
                document.getElementById('infoSize').innerText = info.disk_usage;
                document.getElementById('infoJava').innerText = info.java_version;
                document.getElementById('infoPlayers').innerText = info.player_count + " 명";
            }
        }

        async function openServerJavaManager() {
            const javaInput = document.getElementById('java_path');
            const currentPath = (javaInput && javaInput.value) || "java";
            openModal('javaManagerModal');
            const ctxMsg = document.getElementById('javaManagerContextMsg');
            if (ctxMsg) ctxMsg.innerText = "현재 서버 인스턴스에 할당할 Java 런타임을 아래에서 선택하세요.";
            await loadJavaList(currentPath);
        }

        async function loadJavaList(targetPath = "") {
            const container = document.getElementById('javaListContainer');
            container.innerHTML = "<div style='text-align:center; padding:20px; color:#666;'>검색 중... (Scanning)</div>";

            let list;
            try {
                list = await eel.scan_java_versions_py(targetPath)();
            } catch (err) {
                container.innerHTML = "<div style='text-align:center; padding:20px; color:#f44336;'>오류 발생: " + err.message + "</div>";
                return;
            }
            container.innerHTML = "";

            if (!list || list.length === 0) {
                container.innerHTML = "<div style='text-align:center; padding:20px; color:#666;'>설치된 자바를 발견하지 못했습니다.</div>";
                return;
            }

            list.forEach(java => {
                const item = document.createElement('div');
                item.className = 'list-item';
                item.style.padding = "16px";
                item.style.flexDirection = "column";
                item.style.alignItems = "flex-start";
                item.style.gap = "6px";

                let statusHtml = "";
                let btnHtml = "";
                let bgStyle = "";

                if (java.is_current) {
                    bgStyle = "background: rgba(0, 230, 118, 0.05); border: 1px solid rgba(0, 230, 118, 0.25);";
                    statusHtml = `<span style="font-size:11px; color:var(--accent-green); font-weight:700; margin-bottom:4px;">● 사용 중 (Current Server)</span>`;
                    btnHtml = `<span style="font-size:12px; color:var(--text-sub); font-weight:700;">현재 적용됨</span>`;
                } else {
                    bgStyle = "background: rgba(255, 255, 255, 0.01);";
                    statusHtml = `<span style="font-size:11px; color:#64748b;">설치됨 (Installed)</span>`;
                    btnHtml = `<button class="btn btn-blue" style="padding: 6px 14px; font-size:12px; box-shadow:none;" onclick="applyJavaPath('${java.path.replace(/\\/g, '\\\\')}')">적용하기</button>`;
                }

                item.style.cssText += bgStyle;

                item.innerHTML = `
                    <div style="width:100%; display:flex; justify-content:space-between; align-items:start;">
                        <div style="flex: 1; padding-right: 15px;">
                            ${statusHtml}
                            <div style="font-weight:800; font-size:15px; color:#fff; margin-top: 2px;">Java ${java.version}</div>
                            <div style="font-size:12px; color:var(--text-sub); margin-top:5px; word-break:break-all; font-family:'Fira Code', 'Consolas', monospace;">${java.path}</div>
                        </div>
                        <div style="margin-top: 5px;">
                            ${btnHtml}
                        </div>
                    </div>
                `;
                container.appendChild(item);
            });
        }

        let pendingJavaPath = "";

        function applyJavaPath(path) {
            pendingJavaPath = path;
            openModal('javaApplyConfirmModal');
        }

        async function executeJavaPathChange() {
            closeModal('javaApplyConfirmModal');
            closeModal('javaManagerModal');
            if (!pendingJavaPath) return;

            const javaInput = document.getElementById('java_path');
            if (javaInput) {
                javaInput.value = pendingJavaPath;
                await saveSettings();
            }
        }

        function askKillJava() {
            closeModal('javaHelpModal');
            openModal('killJavaConfirmModal');
        }

        async function executeKillJava() {
            closeModal('killJavaConfirmModal');
            const res = await eel.kill_all_java_processes_py()();
            if (res.includes("✅")) {
                showToast(res, "success");
            } else {
                showToast(res, "error");
            }
        }

        // ==========================================================
        // [추가] 원격 제어 (베타) 관련 JavaScript 제어부
        // ==========================================================
        async function openRemoteSettingsPopup() {
            closeModal('launcherSettingsModal');
            openModal('remoteControlSettingsModal'); setTimeout(refreshAccessLogs, 100);

            // 1. 공인 IP 호출 및 링크 출력 구성
            let ip = "Checking...";
            try {
                if (eel.get_public_ip_py) {
                    ip = await eel.get_public_ip_py()();
                }
            } catch {
                ip = window.location.hostname;
            }
            document.getElementById('remoteAddressLink').innerText = `http://${ip}:8000/index.html`;

            // 2. 기존 설정 연동
            const c = await eel.get_launcher_config_py()();
            document.getElementById('remote_control_enabled_checkbox').checked = (c.remote_enabled === true);
            document.getElementById('remote_control_password_input').value = "";
        }

        async function refreshAccessLogs() {
            const container = document.getElementById('accessLogContainer');
            if (!container) return;
            try {
                const logs = await eel.get_access_logs_py()();
                if (!logs || logs.length === 0) {
                    container.innerHTML = '<div style="color: #666; text-align: center; padding: 20px;">기록 없음</div>';
                    return;
                }
                let html = '<table style="width:100%; border-collapse: collapse;">';
                html += '<tr style="color: var(--accent-cyan); border-bottom: 1px solid rgba(255,255,255,0.1);"><th style="padding:4px 6px; text-align:left;">시간</th><th style="padding:4px 6px; text-align:left;">IP</th><th style="padding:4px 6px; text-align:left;">행동</th><th style="padding:4px 6px; text-align:left;">결과</th><th style="padding:4px 6px; text-align:left;">상세</th></tr>';
                logs.forEach(l => {
                    const color = l.result === 'success' ? '#00e676' : l.result === 'blocked' || l.result === 'fail' ? '#ff5252' : '#ffab40';
                    html += `<tr style="border-bottom: 1px solid rgba(255,255,255,0.04);">
                        <td style="padding:4px 6px; color:#888;">${l.time}</td>
                        <td style="padding:4px 6px; color:#aaa;">${l.ip}</td>
                        <td style="padding:4px 6px; color:#ddd;">${l.action}</td>
                        <td style="padding:4px 6px; color:${color};">${l.result}</td>
                        <td style="padding:4px 6px; color:#999; font-size:10px;">${l.detail || ''}</td>
                    </tr>`;
                });
                html += '</table>';
                container.innerHTML = html;
                container.scrollTop = 0;
            } catch(e) {
                container.innerHTML = '<div style="color: #666; text-align: center; padding: 20px;">로드 실패</div>';
            }
        }
        function copyRemoteAddress() {
            const el = document.getElementById('remoteAddressLink');
            if (!el || !el.innerText || el.innerText === '불러오는 중...') return;
            navigator.clipboard.writeText(el.innerText).then(() => {
                showToast("📋 주소가 복사되었습니다.", "success");
            }).catch(() => {
                const range = document.createRange();
                range.selectNodeContents(el);
                const sel = window.getSelection();
                sel.removeAllRanges(); sel.addRange(range);
                document.execCommand('copy');
                sel.removeAllRanges();
                showToast("📋 주소가 복사되었습니다.", "success");
            });
        }

        async function saveRemoteControlConfig() {
            const isEnabled = document.getElementById('remote_control_enabled_checkbox').checked;
            const newPassword = document.getElementById('remote_control_password_input').value;

            const result = await eel.save_remote_setting_py(isEnabled, newPassword)();
            if (result.includes("✅")) {
                closeModal('remoteControlSettingsModal');
                openModal('restartAppModal');
            } else {
                showToast(result, "error");
            }
        }

        async function executeAppRestart() {
            // 버튼 비활성화 (중복 클릭 방지)
            const btn = document.getElementById('btnAutoRestart');
            if (btn) btn.disabled = true;

            showToast("런처를 재시작하는 중...", "info");

            // 파이썬 측에 재시작 명령 전달
            await eel.restart_launcher_py()();
        }

        // 원격 락 스크린 활성여부 분석 함수
        async function checkRemoteLockScreen() {
            const config = await eel.get_launcher_config_py()();
            if (config && config.remote_enabled === true) {
                // 로컬 전용 토큰이 이미 있는 경우 (localhost 접속) 즉시 통과
                const urlParams = new URLSearchParams(window.location.search);
                if (urlParams.get('token')) return;
                // 이미 인증된 세션이면 통과
                if (window.isEelAuthenticated()) return;

                // 인증되지 않은 경우 강제로 락스크린 모달 노출
                openModal('remoteLockScreenModal');
            }
        }

        async function verifyRemoteLockAuth() {
            const passInput = document.getElementById('remote_auth_password_input');
            const passValue = passInput.value;
            const msgEl = document.getElementById('remoteAuthAttemptMsg');

            const result = await eel.verify_remote_password_py(passValue)();
            if (result && result.success) {
                window.setEelSessionToken(result.token);

                showToast("Authentication successful", "success");

                closeModal('accessRestrictedModal');
                closeModal('remoteLockScreenModal');

                initApp();
            } else {
                const remaining = result ? result.remaining : 0;
                if (remaining <= 0) {
                    msgEl.innerText = "Please try again later.";
                } else {
                    msgEl.innerText = (5 - remaining) + " / 5 attempts failed. " + remaining + " attempts remaining.";
                }
                passInput.value = "";
                passInput.focus();
            }
        }

        function checkRemoteAuthEnter(e) {
            if (e.key === 'Enter') {
                verifyRemoteLockAuth();
            }
        }
    
        // ==========================================================
        // [TUNNEL / AYANAT] 터널 오버레이 로직
        // ==========================================================
        let tunnelState = { logged_in: false, username: "", is_admin: false, credits: 0, plan_credits: 0, bonus_credits: 0, plan: "free", tunnel_active: false, public_address: "" };
        let tunnelCreditsTimer = null;
        document.getElementById("tunnelLoginForm").addEventListener("submit", function (e) {
            e.preventDefault();
            tunnelDoLogin();
        });
        let tunnelSelectedUserId = null;
        let tunnelSelectedUsername = "";

        function openTunnel() {
            const ov = document.getElementById("tunnelOverlay");
            ov.classList.remove("overlay-hidden");
            eel.tunnel_get_tunnel_info_py()().then(info => {
                if (info && info.success && info.logged_in) { tunnelEnterMain(info); }
                else { showTunnelScreen("login"); }
            });
        }
        function closeTunnel() {
            tunnelStopPolling();
            document.getElementById("tunnelOverlay").classList.add("overlay-hidden");
        }
        function showTunnelScreen(name) {
            document.querySelectorAll(".tunnel-screen").forEach(s => s.classList.remove("active"));
            document.getElementById(name === "login" ? "tunnelLogin" : "tunnelMain").classList.add("active");
        }
        async function tunnelDoLogin() {
            const host = "158.179.168.246";
            const port = 42137;
            const user = document.getElementById("tUser").value.trim();
            const pass = document.getElementById("tPass").value;
            const err = document.getElementById("tunnelLoginErr");
            err.textContent = ""; err.className = "tunnel-msg";
            if (!user || !pass) { err.textContent = "아이디와 비밀번호를 입력하세요"; err.className = "tunnel-msg error"; return; }
            const conn = await eel.tunnel_connect_py(host, port)();
            if (!conn.success) { err.textContent = "서버 연결 실패: " + conn.error; err.className = "tunnel-msg error"; return; }
            const res = await eel.tunnel_login_py(user, pass)();
            if (res.success) {
                const info = await eel.tunnel_get_tunnel_info_py()();
                tunnelEnterMain(info);
                await eel.tunnel_start_background_tasks_py()();
                tunnelStartPolling();
            } else {
                err.textContent = res.error || "로그인 실패"; err.className = "tunnel-msg error";
            }
        }
        function tunnelEnterMain(info) {
            if (!info || !info.success) { showTunnelScreen("login"); return; }
            tunnelState.logged_in = info.logged_in;
            tunnelState.username = info.username;
            tunnelState.is_admin = info.is_admin;
            tunnelState.credits = info.credits;
            tunnelState.plan_credits = info.plan_credits;
            tunnelState.bonus_credits = info.bonus_credits;
            tunnelState.plan = info.plan;
            tunnelState.tunnel_active = info.tunnel_active;
            tunnelState.public_address = info.public_address;
            showTunnelScreen("main");
            document.getElementById("tunnelUser").textContent = info.username + (info.is_admin ? " (관리자)" : "");
            tunnelUpdateCredits();
            tunnelSyncTunnelBtn();
        }
        async function tunnelDoLogout() {
            tunnelStopPolling();
            await eel.tunnel_disconnect_py()();
            tunnelState.logged_in = false; tunnelState.tunnel_active = false; tunnelState.public_address = "";
            showTunnelScreen("login");
        }
        async function tunnelToggle() {
            const btn = document.getElementById("tunnelBtn");
            if (tunnelState.tunnel_active) {
                const r = await eel.tunnel_close_tunnel_py()();
                if (r.success) { tunnelState.tunnel_active = false; tunnelState.public_address = ""; tunnelSyncTunnelBtn(); }
            } else {
                const host = document.getElementById("tTargetHost").value.trim() || "127.0.0.1";
                const port = parseInt(document.getElementById("tTargetPort").value.trim() || "25565");
                btn.disabled = true; btn.textContent = "연결중...";
                const r = await eel.tunnel_open_tunnel_py(host, port, "tcp")();
                btn.disabled = false;
                if (r.success) { tunnelState.tunnel_active = true; tunnelState.public_address = r.address; tunnelSyncTunnelBtn(); }
                else { btn.textContent = "터널 열기"; alert("터널 생성 실패: " + (r.error || "알 수 없음")); }
            }
        }
        function tunnelSyncTunnelBtn() {
            const btn = document.getElementById("tunnelBtn");
            const status = document.getElementById("tunnelStatus");
            if (tunnelState.tunnel_active) {
                btn.textContent = "터널 닫기";
                status.style.display = "flex";
                document.getElementById("tunnelDot").className = "status-dot on";
                document.getElementById("tunnelAddr").textContent = tunnelState.public_address;
            } else {
                btn.textContent = "터널 열기";
                status.style.display = "none";
            }
        }
        function tunnelCopyAddr() {
            const addr = document.getElementById("tunnelAddr").textContent;
            if (addr) navigator.clipboard.writeText(addr).then(() => { const b = document.querySelector(".btn-copy"); b.textContent = "복사됨"; setTimeout(() => b.textContent = "복사", 1500); });
        }
        function tunnelUpdateCredits() {
            const el = document.getElementById("tunnelCredits");
            const sub = document.getElementById("tunnelCreditsSub");
            const planEl = document.getElementById("tunnelPlan");
            const credits = tunnelState.credits;
            const plan = tunnelState.plan || "free";
            if (plan === "premium") { el.textContent = "∞"; el.className = "tunnel-credits"; sub.textContent = "무제한"; }
            else {
                el.textContent = (credits || 0).toLocaleString() + "분";
                el.className = "tunnel-credits" + (credits <= 0 ? " danger" : (credits <= 5 ? " warning" : ""));
                const h = Math.floor(credits / 60), m = credits % 60;
                sub.textContent = h > 0 ? h + "시간 " + m + "분" : m + "분";
            }
            const bonus = tunnelState.bonus_credits || 0;
            planEl.textContent = (plan.charAt(0).toUpperCase() + plan.slice(1)) + (plan !== "premium" ? " · " + tunnelState.plan_credits + "분" + (bonus > 0 ? " + 보너스 " + bonus : "") : "");
        }
        function tunnelStartPolling() {
            tunnelStopPolling();
            tunnelCreditsTimer = setInterval(async () => {
                if (!tunnelState.logged_in) return;
                const st = await eel.tunnel_get_status_py()();
                if (st.success && st.session_count !== undefined) {
                    document.getElementById("tunnelBusyBanner").style.display = st.session_count >= 4 ? "flex" : "none";
                }
                const info = await eel.tunnel_get_tunnel_info_py()();
                if (info.success) {
                    tunnelState.credits = info.credits; tunnelState.plan = info.plan; tunnelState.plan_credits = info.plan_credits; tunnelState.bonus_credits = info.bonus_credits;
                    tunnelState.tunnel_active = info.tunnel_active; tunnelState.public_address = info.public_address;
                    tunnelUpdateCredits(); tunnelSyncTunnelBtn();
                    if (tunnelState.tunnel_active) tunnelRefreshConns();
                }
            }, 3000);
        }
        function tunnelStopPolling() { if (tunnelCreditsTimer) { clearInterval(tunnelCreditsTimer); tunnelCreditsTimer = null; } }
        async function tunnelRefreshConns() {
            const r = await eel.tunnel_get_connections_py()();
            const el = document.getElementById("tunnelConns");
            if (!r.success) return;
            const conns = r.connections || [];
            if (conns.length === 0) { el.innerHTML = '<div class="conn-empty">접속자가 없습니다</div>'; return; }
            const groups = {};
            conns.forEach(c => { (groups[c.ip] = groups[c.ip] || []).push(c); });
            el.innerHTML = "";
            for (const ip in groups) {
                const list = groups[ip];
                const g = document.createElement("div"); g.className = "conn-group";
                const hdr = document.createElement("div"); hdr.className = "conn-group-header";
                hdr.innerHTML = '<span class="conn-group-ip">' + ip + ' (' + list.length + ')</span>';
                g.appendChild(hdr);
                list.forEach(c => {
                    const item = document.createElement("div"); item.className = "conn-child";
                    const mins = Math.floor(c.seconds / 60), secs = c.seconds % 60;
                    item.innerHTML = '<div class="conn-child-info"><div class="conn-child-addr">' + c.port + (c.proto ? " " + c.proto.toUpperCase() : "") + '</div><div class="conn-child-meta">' + (mins > 0 ? mins + "분 " : "") + secs + "초</div></div>";
                    const kb = document.createElement("button"); kb.className = "btn-kick"; kb.textContent = "끊기"; kb.onclick = () => eel.tunnel_kick_connection_py(c.conn_id)().then(() => tunnelRefreshConns());
                    item.appendChild(kb); g.appendChild(item);
                });
                el.appendChild(g);
            }
        }

        async function tunnelChangePassword() {
            const cur = document.getElementById("tPwCurrent").value;
            const nw = document.getElementById("tPwNew").value;
            const cf = document.getElementById("tPwConfirm").value;
            const msg = document.getElementById("tPwMsg");
            msg.textContent = ""; msg.className = "tunnel-msg";
            if (!cur) { msg.textContent = "현재 비밀번호를 입력하세요"; msg.className = "tunnel-msg error"; return; }
            if (!nw || nw.length < 4) { msg.textContent = "새 비밀번호는 4자 이상 입력하세요"; msg.className = "tunnel-msg error"; return; }
            if (nw !== cf) { msg.textContent = "새 비밀번호가 일치하지 않습니다"; msg.className = "tunnel-msg error"; return; }
            const r = await eel.tunnel_change_password_py(cur, nw)();
            if (r.success) {
                msg.textContent = "✅ 비밀번호가 변경되었습니다"; msg.className = "tunnel-msg success";
                document.getElementById("tPwCurrent").value = "";
                document.getElementById("tPwNew").value = "";
                document.getElementById("tPwConfirm").value = "";
                setTimeout(() => { closeModal("tunnelChangePwModal"); msg.textContent = ""; }, 1200);
            } else {
                msg.textContent = "❌ " + (r.error || "변경 실패"); msg.className = "tunnel-msg error";
            }
        }

        // ==========================================================
        // [UPDATE] OTA 업데이트 로직
        // ==========================================================
        let _updateData = null;
        let _updatePollTimer = null;

        async function checkUpdate() {
            openModal('updateModal');
            document.getElementById('updateStatus').textContent = '업데이트를 확인하는 중...';
            document.getElementById('updateProgress').style.display = 'none';
            document.getElementById('updateNotes').style.display = 'none';
            document.getElementById('updateCloseBtn').style.display = 'none';
            document.getElementById('updateDownloadBtn').style.display = 'none';
            try {
                const r = await eel.check_update_py()();
                if (!r.success) {
                    document.getElementById('updateStatus').textContent = '❌ 확인 실패: ' + (r.error || '알 수 없음');
                    document.getElementById('updateCloseBtn').style.display = '';
                    return;
                }
                _updateData = r;
                if (!r.has_update) {
                    document.getElementById('updateStatus').textContent = '✅ 최신 버전입니다 (v' + r.current_version + ')';
                    document.getElementById('updateCloseBtn').style.display = '';
                    return;
                }
                document.getElementById('updateStatus').innerHTML =
                    '<span style="color:var(--accent-green);">새 버전 발견!</span><br>' +
                    '<span style="font-size:12px; color:var(--text-sub);">v' + r.current_version + ' → v' + r.latest_version + '</span>';
                if (r.release_notes) {
                    document.getElementById('updateNotes').style.display = '';
                    document.getElementById('updateNotes').innerHTML = '<strong>변경사항:</strong><br>' + r.release_notes.replace(/\n/g, '<br>');
                }
                document.getElementById('updateDownloadBtn').style.display = '';
                document.getElementById('updateCloseBtn').style.display = '';
            } catch (e) {
                document.getElementById('updateStatus').textContent = '❌ 오류: ' + e.message;
                document.getElementById('updateCloseBtn').style.display = '';
            }
        }

        async function downloadUpdate() {
            if (!_updateData || !_updateData.asset_url) return;
            document.getElementById('updateDownloadBtn').style.display = 'none';
            document.getElementById('updateProgress').style.display = '';
            document.getElementById('updateStatus').textContent = '다운로드 중...';
            try {
                await eel.download_update_py(_updateData.asset_url, _updateData.asset_name)();
                _updatePollTimer = setInterval(pollUpdateProgress, 500);
            } catch (e) {
                document.getElementById('updateStatus').textContent = '❌ 다운로드 실패: ' + e.message;
                document.getElementById('updateCloseBtn').style.display = '';
            }
        }

        async function pollUpdateProgress() {
            try {
                const p = await eel.get_update_progress_py()();
                document.getElementById('updateProgressBar').style.width = p.percent + '%';
                document.getElementById('updatePercent').textContent = p.percent + '%';
                document.getElementById('updateStatus').textContent = p.status;
                if (p.error) {
                    clearInterval(_updatePollTimer);
                    document.getElementById('updateStatus').textContent = '❌ ' + p.error;
                    document.getElementById('updateCloseBtn').style.display = '';
                }
                if (!p.active && p.percent >= 100) {
                    clearInterval(_updatePollTimer);
                    document.getElementById('updateStatus').textContent = '✅ 다운로드 완료. 적용 중...';
                    document.getElementById('updatePercent').textContent = '재시작합니다...';
                    setTimeout(async () => {
                        await eel.apply_update_py()();
                    }, 1000);
                }
            } catch (e) {
                clearInterval(_updatePollTimer);
            }
        }
