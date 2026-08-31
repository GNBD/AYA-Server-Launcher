var creditsTimer = null;
var selectedUserId = null;
var selectedUsername = "";
var selectedProto = "tcp";
var state = {
    logged_in: false,
    username: "",
    is_admin: false,
    credits: 0,
    plan_credits: 0,
    bonus_credits: 0,
    plan: "free",
    tunnel_active: false,
    public_address: ""
};

function showScreen(id) {
    document.querySelectorAll('.screen').forEach(function(s) { s.classList.remove('active'); });
    document.getElementById(id).classList.add('active');
}

function setResult(id, msg, isError) {
    var el = document.getElementById(id);
    if (el) {
        el.textContent = msg;
        el.className = isError ? 'msg-error' : 'msg-success';
    }
}

async function apiCall(name, data) {
    try {
        var resp = await fetch('/api/' + name, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data || {})
        });
        return await resp.json();
    } catch (e) {
        console.error('[AYANAT] api 오류', name, e);
        return { success: false, error: '요청 실패: ' + e.message };
    }
}

async function refreshState() {
    var info = await apiCall('get_tunnel_info', {});
    if (info.success) {
        state.logged_in = info.logged_in;
        state.username = info.username;
        state.is_admin = info.is_admin;
        state.credits = info.credits;
        state.plan_credits = info.plan_credits;
        state.bonus_credits = info.bonus_credits;
        state.plan = info.plan;
        state.tunnel_active = info.tunnel_active;
        state.public_address = info.public_address;
    }
    return info;
}

function switchTab(name) {
    document.querySelectorAll('.tab-content').forEach(function(t) { t.classList.remove('active'); });
    document.querySelectorAll('.nav-item').forEach(function(b) { b.classList.remove('active'); });
    document.getElementById('tab-' + name).classList.add('active');
    var btn = document.querySelector('.nav-item[data-tab="' + name + '"]');
    if (btn) btn.classList.add('active');
    if (name === 'admin') { refreshUsers(); refreshPlanRequests(); }
}

function selectProto(proto, el) {
    selectedProto = proto;
    document.querySelectorAll('.proto-opt').forEach(function(b) { b.classList.remove('active'); });
    el.classList.add('active');
}

async function doLogin() {
    var username = document.getElementById('login-username').value;
    var password = document.getElementById('login-password').value;
    if (!username || !password) {
        setResult('login-error', '아이디와 비밀번호를 입력하세요', true);
        return;
    }
    var conn = await apiCall('connect', {
        server_host: '158.179.168.246',
        server_port: 42137
    });
    if (!conn.success) {
        setResult('login-error', '서버 연결 실패: ' + conn.error, true);
        return;
    }
    var result = await apiCall('login', { username: username, password: password });
    if (result.success) {
        await refreshState();
        document.getElementById('user-info').textContent = state.username + (state.is_admin ? ' (관리자)' : '');
        showScreen('main-screen');
        setResult('login-error', '', false);
        await apiCall('start_background_tasks', {});
        if (state.is_admin) {
            document.getElementById('admin-tab-btn').style.display = '';
        }
        updateCreditsDisplay();
        startCreditsPolling();
        checkNotice();
    } else {
        setResult('login-error', result.error, true);
    }
}

async function doLogout() {
    stopCreditsPolling();
    await apiCall('disconnect', {});
    showScreen('login-screen');
    document.getElementById('admin-tab-btn').style.display = 'none';
    document.getElementById('server-busy-banner').style.display = 'none';
    switchTab('tunnel');
    var btn = document.getElementById('tunnel-btn');
    btn.textContent = '터널 열기';
    btn.classList.remove('active');
    btn.disabled = false;
    hideAllPanels();
    state.logged_in = false;
    state.tunnel_active = false;
    state.public_address = '';
    document.querySelectorAll('.proto-opt').forEach(function(b) { b.classList.remove('active'); });
    document.querySelector('.proto-opt').classList.add('active');
    selectedProto = 'tcp';
}

async function toggleTunnel() {
    var btn = document.getElementById('tunnel-btn');
    if (state.tunnel_active) {
        var result = await apiCall('close_tunnel', {});
        if (result.success) {
            state.tunnel_active = false;
            state.public_address = '';
            btn.textContent = '터널 열기';
            btn.classList.remove('active');
            document.getElementById('tunnel-status').style.display = 'none';
            document.querySelectorAll('.proto-opt').forEach(function(b) { b.style.pointerEvents = ''; });
        }
    } else {
        var host = document.getElementById('target-host').value || '127.0.0.1';
        var port = document.getElementById('target-port').value || '25565';
        btn.disabled = true;
        btn.textContent = '연결중...';
        await new Promise(function(res) { setTimeout(res, 3000); });
        var result2 = await apiCall('open_tunnel', { target_host: host, target_port: parseInt(port), proto: selectedProto });
        btn.disabled = false;
        if (result2.success) {
            state.tunnel_active = true;
            state.public_address = result2.address;
            btn.textContent = '터널 닫기';
            btn.classList.add('active');
            document.getElementById('tunnel-status').style.display = 'block';
            document.getElementById('status-indicator').className = 'status-dot on';
            document.getElementById('public-address').textContent = result2.address;
            document.querySelectorAll('.proto-opt').forEach(function(b) { b.style.pointerEvents = 'none'; });
            refreshConnections();
        } else {
            btn.textContent = '터널 열기';
            alert('터널 생성 실패: ' + result2.error);
        }
    }
}

async function refreshConnections() {
    if (!state.tunnel_active) return;
    var r = await apiCall('get_connections', {});
    if (!r.success) return;
    var el = document.getElementById('conn-list');
    if (!el) return;
    var conns = r.connections || [];
    var expanded = {};
    el.querySelectorAll('.conn-group').forEach(function(g) {
        var ip = g.getAttribute('data-ip');
        var body = g.querySelector('.conn-group-body');
        if (body && body.style.display === 'block') expanded[ip] = true;
    });
    el.innerHTML = '';
    if (conns.length === 0) {
        el.innerHTML = '<div class="conn-empty">접속자가 없습니다</div>';
        return;
    }
    var groups = {};
    for (var i = 0; i < conns.length; i++) {
        var c = conns[i];
        if (!groups[c.ip]) groups[c.ip] = [];
        groups[c.ip].push(c);
    }
    for (var ip in groups) {
        var list = groups[ip];
        var group = document.createElement('div');
        group.className = 'conn-group';
        group.setAttribute('data-ip', ip);
        var header = document.createElement('div');
        header.className = 'conn-group-header';
        header.innerHTML =
            '<span class="conn-group-ip">' + ip + ' (' + list.length + ')</span>' +
            '<button class="conn-group-toggle" onclick="toggleConnGroup(\'' + ip + '\')">' + (expanded[ip] ? '&#9660;' : '&#9654;') + '</button>';
        group.appendChild(header);
        var body = document.createElement('div');
        body.className = 'conn-group-body';
        body.style.display = expanded[ip] ? 'block' : 'none';
        for (var j = 0; j < list.length; j++) {
            var c = list[j];
            var item = document.createElement('div');
            item.className = 'conn-child';
            var rttColor = c.rtt_ms > 0 ? (c.rtt_ms < 80 ? 'var(--success)' : (c.rtt_ms < 150 ? 'var(--warning)' : 'var(--danger)')) : 'var(--text3)';
            var mins = Math.floor(c.seconds / 60);
            var secs = c.seconds % 60;
            item.innerHTML =
                '<div class="conn-child-info">' +
                    '<div class="conn-child-addr">' + c.port +
                        (c.proto ? ' <span style="font-size:10px;color:var(--text3);margin-left:4px;">' + c.proto.toUpperCase() + '</span>' : '') +
                    '</div>' +
                    '<div class="conn-child-meta">' +
                        (mins > 0 ? mins + '분 ' : '') + secs + '초 &middot; ' +
                        '<span style="color:' + rttColor + ';">핑 ' + c.rtt_ms + 'ms</span> &middot; ' +
                        '&#9660;' + c.rx_kbps + 'k &#9650;' + c.tx_kbps + 'k' +
                    '</div>' +
                '</div>' +
                '<div class="conn-child-actions">' +
                    '<button class="btn-kick" onclick="kickConnection(\'' + c.conn_id + '\')">끊기</button>' +
                '</div>';
            body.appendChild(item);
        }
        group.appendChild(body);
        el.appendChild(group);
    }
}

function toggleConnGroup(ip) {
    var group = document.querySelector('.conn-group[data-ip="' + ip + '"]');
    if (!group) return;
    var body = group.querySelector('.conn-group-body');
    var toggle = group.querySelector('.conn-group-toggle');
    if (!body || !toggle) return;
    if (body.style.display === 'none') {
        body.style.display = 'block';
        toggle.innerHTML = '&#9660;';
    } else {
        body.style.display = 'none';
        toggle.innerHTML = '&#9654;';
    }
}

async function kickConnection(connId) {
    var r = await apiCall('kick_connection', { conn_id: connId });
    if (r.success) {
        refreshConnections();
    } else {
        alert('끊기 실패: ' + r.error);
    }
}

function copyAddress() {
    var addr = document.getElementById('public-address').textContent;
    if (addr && addr !== '-') {
        navigator.clipboard.writeText(addr).then(function() {
            var btn = document.querySelector('.btn-copy');
            btn.textContent = '복사됨';
            setTimeout(function() { btn.textContent = '복사'; }, 1500);
        });
    }
}

function updateCreditsDisplay() {
    var el = document.getElementById('credits-display');
    var sub = document.getElementById('credits-time');
    var planEl = document.getElementById('credits-plan');
    var credits = state.credits;
    var planName = state.plan || 'free';
    if (planName === 'premium') {
        el.textContent = '∞';
        el.className = 'credits-value';
        sub.textContent = '무제한';
    } else {
        el.textContent = credits.toLocaleString() + '분';
        el.className = 'credits-value';
        if (credits <= 0) { el.className += ' danger'; }
        else if (credits <= 5) { el.className += ' warning'; }
        var hours = Math.floor(credits / 60);
        var mins = credits % 60;
        sub.textContent = hours > 0 ? hours + '시간 ' + mins + '분' : mins + '분';
    }
    if (planEl) {
        var bonus = state.bonus_credits || 0;
        var planLabel = planName.charAt(0).toUpperCase() + planName.slice(1);
        planEl.textContent = planLabel + (planName !== 'premium' ? ' · ' + state.plan_credits + '분' + (bonus > 0 ? ' + 보너스 ' + bonus : '') : '');
    }
    if (state.tunnel_active) {
        document.getElementById('status-indicator').className = 'status-dot on';
        document.getElementById('public-address').textContent = state.public_address;
    }
}

function startCreditsPolling() {
    stopCreditsPolling();
    creditsTimer = setInterval(async function() {
        if (!state.logged_in) return;
        var status = await apiCall('get_status', {});
        if (status.success && status.session_count !== undefined) {
            var banner = document.getElementById('server-busy-banner');
            if (status.session_count >= 4) {
                banner.style.display = 'flex';
            } else {
                banner.style.display = 'none';
            }
        }
        await refreshState();
        await refreshState();
        updateCreditsDisplay();
        if (state.tunnel_active) {
            refreshConnections();
        } else {
            if (document.getElementById('tunnel-status').style.display === 'block') {
                document.getElementById('tunnel-status').style.display = 'none';
                var btn = document.getElementById('tunnel-btn');
                btn.textContent = '터널 열기';
                btn.classList.remove('active');
            }
            var cl = document.getElementById('conn-list');
            if (cl) cl.innerHTML = '';
        }
    }, 3000);
}

function stopCreditsPolling() {
    if (creditsTimer) { clearInterval(creditsTimer); creditsTimer = null; }
}

/* ===== 공지 시스템 ===== */

async function checkNotice() {
    var r = await apiCall('get_notice', {});
    if (!r.success || !r.notice) return;
    var nid = String(r.notice_id);
    var shown = localStorage.getItem('ayanat_notice_shown');
    if (shown === nid) return;
    localStorage.setItem('ayanat_notice_shown', nid);
    showNoticeModal(r.notice);
}

function showNoticeModal(notice) {
    var modal = document.getElementById('notice-modal');
    document.getElementById('notice-text').textContent = notice;
    modal.style.display = 'flex';
}

function closeNoticeModal() {
    document.getElementById('notice-modal').style.display = 'none';
}

async function doSetNotice() {
    var notice = document.getElementById('notice-input').value;
    var result = await apiCall('set_notice', { notice: notice });
    if (result.success) {
        setResult('notice-result', '공지가 등록되었습니다', false);
    } else {
        setResult('notice-result', result.error, true);
    }
}

async function doClearNotice() {
    var result = await apiCall('set_notice', { notice: '' });
    if (result.success) {
        document.getElementById('notice-input').value = '';
        setResult('notice-result', '공지가 해제되었습니다', false);
    } else {
        setResult('notice-result', result.error, true);
    }
}

/* ===== 요금제 신청 (일반 사용자) ===== */

function showPlanRequestDialog() {
    var wrap = document.getElementById('plan-request-area');
    if (!wrap) return;
    wrap.innerHTML = '';
    var plans = [
                        { v: 'free',     label: 'Free · 250kbps · 하루 100분' },
                        { v: 'standard', label: 'Standard · 750kbps · 하루 300분' },
                        { v: 'premium',  label: 'Premium · 1500kbps · 무제한' }
    ];
    var selWrap = document.createElement('div');
    selWrap.className = 'plan-select-wrap';
    var sel = document.createElement('select');
    sel.innerHTML = plans.map(function(p) {
        return '<option value="' + p.v + '">' + p.label + '</option>';
    }).join('');
    selWrap.appendChild(sel);
    var btnRow = document.createElement('div');
    btnRow.className = 'btn-grid';
    btnRow.style.marginTop = '10px';
    var okBtn = document.createElement('button');
    okBtn.textContent = '신청';
    okBtn.className = 'btn-primary';
    okBtn.style.flex = '2';
    okBtn.onclick = function() {
        var v = sel.value;
        wrap.innerHTML = '';
        requestPlan(v);
    };
    var cancelBtn = document.createElement('button');
    cancelBtn.textContent = '취소';
    cancelBtn.className = 'btn-secondary';
    cancelBtn.onclick = function() {
        wrap.innerHTML = '';
    };
    btnRow.appendChild(okBtn);
    btnRow.appendChild(cancelBtn);
    var msg = document.createElement('div');
    msg.textContent = '관리자 승인 후 적용됩니다';
    msg.style.cssText = 'font-size:12px;color:var(--text3);margin-bottom:10px;';
    wrap.appendChild(msg);
    wrap.appendChild(selWrap);
    wrap.appendChild(btnRow);
}

async function requestPlan(plan) {
    var result = await apiCall('request_plan', { plan: plan });
    if (result.success) {
        alert('요금제 신청 완료! 관리자 승인을 기다리세요.');
        var wrap = document.getElementById('plan-request-area');
        if (wrap) wrap.innerHTML = '';
    } else {
        alert('요금제 신청 실패: ' + result.error);
    }
}

async function refreshPlanRequests() {
    var result = await apiCall('list_plan_requests', {});
    if (!result.success) return;
    var el = document.getElementById('plan-request-list');
    if (!el) return;
    el.innerHTML = '';
    var pending = result.requests.filter(function(r) { return r.status === 'pending'; });
    if (pending.length === 0) {
        el.innerHTML = '<div class="conn-empty">대기 중인 신청이 없습니다</div>';
        return;
    }
    for (var i = 0; i < pending.length; i++) {
        var r = pending[i];
        var item = document.createElement('div');
        item.className = 'plan-req-item';
        item.innerHTML =
            '<div class="plan-req-info">' +
                '<div class="plan-req-user">' + r.username + '</div>' +
                '<div class="plan-req-plan">' + r.requested_plan + ' 신청</div>' +
            '</div>' +
            '<div class="plan-req-actions">' +
                '<button class="btn-approve" onclick="resolvePlanRequest(' + r.id + ', true)">승인</button>' +
                '<button class="btn-reject" onclick="resolvePlanRequest(' + r.id + ', false)">거절</button>' +
            '</div>';
        el.appendChild(item);
    }
}

async function resolvePlanRequest(requestId, approve) {
    var result = await apiCall('resolve_plan_request', { request_id: requestId, approve: approve });
    if (result.success) {
        alert(approve ? '승인 완료!' : '거절되었습니다');
        refreshPlanRequests();
        refreshUsers();
    } else {
        alert('처리 실패: ' + result.error);
    }
}

async function setUserPlan(userId, plan) {
    var result = await apiCall('set_plan', { user_id: userId, plan: plan });
    if (result.success) {
        refreshUsers();
    } else {
        alert('변경 실패: ' + result.error);
    }
}

/* ===== 관리자 기능 ===== */

function hideAllPanels() {
    document.getElementById('credit-panel').style.display = 'none';
    document.getElementById('ban-panel').style.display = 'none';
    document.getElementById('log-panel').style.display = 'none';
    selectedUserId = null;
    selectedUsername = '';
}

async function refreshUsers() {
    var result = await apiCall('list_users', {});
    if (!result.success) return;
    var el = document.getElementById('user-list');
    el.innerHTML = '';
    for (var i = 0; i < result.users.length; i++) {
        var u = result.users[i];
        var card = document.createElement('div');
        card.className = 'user-card' + (selectedUserId === u.id ? ' selected' : '');
        card.onclick = (function(uid, uname) {
            return function() { selectUser(uid, uname); };
        })(u.id, u.username);

        var avatarClass = u.is_banned ? 'banned' : (u.connected ? 'online' : 'offline');
        var initial = u.username.charAt(0).toUpperCase();
        var planName = u.plan ? u.plan : 'free';
        var bonus = u.bonus_credits || 0;
        var totalCredits = u.credits + bonus;
        var statusText = u.is_banned ? '제재됨' : (u.connected ? '연결됨' : '오프라인');

        var planSel = '';
        if (!u.is_admin) {
            planSel = '<select class="plan-sel" onclick="event.stopPropagation()" onchange="setUserPlan(' + u.id + ', this.value)">' +
                '<option value="free"' + (planName === 'free' ? ' selected' : '') + '>Free</option>' +
                '<option value="standard"' + (planName === 'standard' ? ' selected' : '') + '>Standard</option>' +
                '<option value="premium"' + (planName === 'premium' ? ' selected' : '') + '>Premium</option>' +
                '</select>';
        }

        card.innerHTML =
            '<div class="user-avatar ' + avatarClass + '">' + initial + '</div>' +
            '<div class="user-info">' +
                '<div class="user-name">' + u.username + (u.is_admin ? ' <span style="color:var(--accent);font-size:11px;">관리자</span>' : '') + '</div>' +
                '<div class="user-meta">' +
                    '<span class="user-plan-badge ' + planName + '">' + planName + '</span>' +
                    '<span>' + totalCredits.toLocaleString() + '분</span>' +
                    '<span>' + statusText + '</span>' +
                '</div>' +
            '</div>' +
            (planSel ? '<div onclick="event.stopPropagation()">' + planSel + '</div>' : '') +
            '<button class="btn-kick" onclick="event.stopPropagation();viewUserLog(' + u.id + ',\'' + u.username + '\')">로그</button>';
        el.appendChild(card);
    }
}

function selectUser(userId, username) {
    selectedUserId = userId;
    selectedUsername = username;
    document.getElementById('credit-target').textContent = username;
    document.getElementById('ban-target').textContent = username;
    document.getElementById('credit-panel').style.display = 'block';
    document.getElementById('ban-panel').style.display = 'block';
    setResult('credit-result', '', false);
    setResult('ban-result', '', false);
    document.querySelectorAll('.user-card').forEach(function(c) { c.classList.remove('selected'); });
    event.currentTarget.classList.add('selected');
}

async function doCreateUser() {
    var username = document.getElementById('new-username').value;
    var password = document.getElementById('new-password').value;
    var credits = document.getElementById('new-credits').value;
    if (!username || !password) {
        setResult('create-result', '아이디와 비밀번호를 입력하세요', true);
        return;
    }
    var result = await apiCall('create_user', { username: username, password: password, credits: parseInt(credits || 0) });
    if (result.success) {
        setResult('create-result', "사용자 '" + username + "' 생성 완료", false);
        document.getElementById('new-username').value = '';
        document.getElementById('new-password').value = '';
        document.getElementById('new-credits').value = '0';
        refreshUsers();
    } else {
        setResult('create-result', result.error, true);
    }
}

async function doAddCredits() {
    if (!selectedUserId) return;
    var amount = document.getElementById('credit-amount').value;
    var result = await apiCall('add_credits', { user_id: selectedUserId, amount: parseInt(amount) });
    if (result.success) {
        setResult('credit-result', '+' + amount + ' 크레딧 추가 (잔액: ' + result.new_balance + ')', false);
        refreshUsers();
    } else {
        setResult('credit-result', result.error, true);
    }
}

async function doRemoveCredits() {
    if (!selectedUserId) return;
    var amount = document.getElementById('credit-amount').value;
    var result = await apiCall('remove_credits', { user_id: selectedUserId, amount: parseInt(amount) });
    if (result.success) {
        setResult('credit-result', '-' + amount + ' 크레딧 제거 (잔액: ' + result.new_balance + ')', false);
        refreshUsers();
    } else {
        setResult('credit-result', result.error, true);
    }
}

async function doSetCredits() {
    if (!selectedUserId) return;
    var amount = document.getElementById('set-credit-amount').value;
    var result = await apiCall('set_credits', { user_id: selectedUserId, amount: parseInt(amount) });
    if (result.success) {
        setResult('credit-result', '크레딧 설정: ' + result.new_balance, false);
        refreshUsers();
    } else {
        setResult('credit-result', result.error, true);
    }
}

async function doBanUser() {
    if (!selectedUserId) return;
    var reason = document.getElementById('ban-reason').value;
    var result = await apiCall('ban_user', { user_id: selectedUserId, reason: reason });
    if (result.success) {
        setResult('ban-result', "'" + selectedUsername + "' 제재 완료", false);
        refreshUsers();
    } else {
        setResult('ban-result', result.error, true);
    }
}

async function doUnbanUser() {
    if (!selectedUserId) return;
    var result = await apiCall('unban_user', { user_id: selectedUserId });
    if (result.success) {
        setResult('ban-result', "'" + selectedUsername + "' 제재 해제 완료", false);
        refreshUsers();
    } else {
        setResult('ban-result', result.error, true);
    }
}

async function doForceDisconnect() {
    if (!selectedUserId) return;
    var result = await apiCall('force_disconnect', { user_id: selectedUserId });
    if (result.success) {
        setResult('ban-result', '강제 연결 해제 완료 (' + result.count + '개 세션)', false);
        refreshUsers();
    } else {
        setResult('ban-result', result.error, true);
    }
}

async function doForceCloseTunnels() {
    if (!selectedUserId) return;
    var result = await apiCall('force_close_tunnels', { user_id: selectedUserId });
    if (result.success) {
        setResult('ban-result', '강제 터널 종료 완료 (' + result.count + '개 터널)', false);
        refreshUsers();
    } else {
        setResult('ban-result', result.error, true);
    }
}

async function doDeleteUser() {
    if (!selectedUserId) return;
    if (!confirm("'" + selectedUsername + "' 사용자를 정말 삭제하시겠습니까?")) return;
    var result = await apiCall('delete_user', { user_id: selectedUserId });
    if (result.success) {
        setResult('ban-result', "'" + selectedUsername + "' 계정 삭제 완료", false);
        hideAllPanels();
        refreshUsers();
    } else {
        setResult('ban-result', result.error, true);
    }
}

async function doChangePassword() {
    var old_pw = document.getElementById('pw-old').value;
    var new_pw = document.getElementById('pw-new').value;
    var new_pw2 = document.getElementById('pw-new2').value;
    if (!old_pw || !new_pw) {
        setResult('pw-result', '비밀번호를 입력하세요', true);
        return;
    }
    if (new_pw !== new_pw2) {
        setResult('pw-result', '새 비밀번호가 일치하지 않습니다', true);
        return;
    }
    if (new_pw.length < 4) {
        setResult('pw-result', '새 비밀번호는 4자 이상이어야 합니다', true);
        return;
    }
    var result = await apiCall('change_password', { old_password: old_pw, new_password: new_pw });
    if (result.success) {
        setResult('pw-result', '비밀번호가 변경되었습니다', false);
        document.getElementById('pw-old').value = '';
        document.getElementById('pw-new').value = '';
        document.getElementById('pw-new2').value = '';
    } else {
        setResult('pw-result', result.error, true);
    }
}

async function doResetPassword() {
    if (!selectedUserId) return;
    var new_pw = document.getElementById('reset-pw').value;
    if (!new_pw) {
        setResult('ban-result', '새 비밀번호를 입력하세요', true);
        return;
    }
    var result = await apiCall('set_password', { user_id: selectedUserId, new_password: new_pw });
    if (result.success) {
        setResult('ban-result', "'" + selectedUsername + "' 비밀번호 초기화 완료", false);
        document.getElementById('reset-pw').value = '';
    } else {
        setResult('ban-result', result.error, true);
    }
}

function viewUserLog(userId, username) {
    selectedUserId = userId;
    selectedUsername = username;
    document.getElementById('log-target').textContent = username;
    document.getElementById('log-panel').style.display = 'block';
    document.getElementById('log-content').textContent = '불러오는 중...';
    setResult('log-result', '', false);
    refreshUserLog();
}

async function refreshUserLog() {
    if (!selectedUserId) return;
    var result = await apiCall('get_user_log', { user_id: selectedUserId });
    if (result.success) {
        document.getElementById('log-content').textContent = result.log || '(로그 없음)';
    } else {
        document.getElementById('log-content').textContent = result.error;
    }
}

async function doDeleteUserLog() {
    if (!selectedUserId) return;
    if (!confirm("'" + selectedUsername + "' 사용자의 로그를 삭제하시겠습니까?")) return;
    var result = await apiCall('delete_user_log', { user_id: selectedUserId });
    if (result.success) {
        setResult('log-result', '로그 삭제 완료', false);
        document.getElementById('log-content').textContent = '(로그 없음)';
    } else {
        setResult('log-result', result.error, true);
    }
}
