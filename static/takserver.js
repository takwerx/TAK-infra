async function resyncLdap(){
    if(!confirm("Resync will restart the Authentik worker and re-apply the LDAP blueprint. The TAK Portal user list may take a short moment to repopulate.\\n\\nContinue?")){return;}
    var btn=document.getElementById('resync-ldap-btn');
    var msg=document.getElementById('resync-ldap-msg');
    if(btn){btn.disabled=true;btn.style.opacity='0.7';btn.textContent='Resyncing...';}
    if(msg){msg.textContent='';msg.style.color='var(--text-dim)';}
    try{
        var r=await fetch('/api/takserver/connect-ldap',{method:'POST',headers:{'Content-Type':'application/json'}});
        var d=await r.json();
        if(d.success){
            if(msg){msg.textContent=d.message||'Done.';msg.style.color='var(--green)';}
            var notice=document.getElementById('resync-notice');
            if(notice){notice.style.display='block';window.setTimeout(function(){notice.style.display='none';},10000);}
            if(btn){btn.disabled=false;btn.style.opacity='1';btn.textContent='Resync LDAP to TAK Server';}
        }
        else{if(msg){msg.textContent=d.message||'Failed';msg.style.color='var(--red)';} if(btn){btn.disabled=false;btn.style.opacity='1';btn.textContent='Resync LDAP to TAK Server';}}
    }
    catch(e){if(msg){msg.textContent='Error: '+e.message;msg.style.color='var(--red)';} if(btn){btn.disabled=false;btn.style.opacity='1';btn.textContent='Resync LDAP to TAK Server';}}
}
async function showWebadminPassword(){
    var btn=document.getElementById('webadmin-pw-btn');
    var display=document.getElementById('webadmin-pw-display');
    if(!btn||!display)return;
    if(display.style.display==='inline'){display.style.display='none';display.textContent='';btn.textContent='🔑 Show Password';return;}
    try{
        var r=await fetch('/api/takserver/webadmin-password');
        var d=await r.json();
        if(d.password){display.textContent=d.password;display.style.display='inline';btn.textContent='🔑 Hide';}
        else{display.textContent='Not set (set at deploy or sync webadmin)';display.style.display='inline';}
    }catch(e){display.textContent='Error';display.style.display='inline';}
}
async function syncWebadmin(){
    var btn=document.getElementById('sync-webadmin-btn');
    var msg=document.getElementById('sync-webadmin-msg');
    if(btn){btn.disabled=true;btn.style.opacity='0.7';}
    if(msg){msg.textContent='Syncing...';msg.style.color='var(--text-dim)';}
    try{
        var r=await fetch('/api/takserver/sync-webadmin',{method:'POST',headers:{'Content-Type':'application/json'}});
        var d=await r.json();
        if(d.success){if(msg){msg.textContent=d.message||'Synced.';msg.style.color='var(--green)';} if(btn){btn.disabled=false;btn.style.opacity='1';}}
        else{if(msg){msg.textContent=d.error||d.message||'Failed';msg.style.color='var(--red)';} if(btn){btn.disabled=false;btn.style.opacity='1';}}
    }
    catch(e){if(msg){msg.textContent='Error: '+e.message;msg.style.color='var(--red)';} if(btn){btn.disabled=false;btn.style.opacity='1';}}
}
async function loadServices(){
    var el=document.getElementById('services-list');
    if(!el)return;
    try{
        var r=await fetch('/api/takserver/services');
        var d=await r.json();
        if(!d.services||d.services.length===0){el.textContent='No services detected';return}
        var h='<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px">';
        d.services.forEach(function(s){
            var color=s.status==='running'?'var(--green)':'var(--red)';
            var dot=s.status==='running'?'●':'○';
            h+='<div style="background:var(--bg-surface);border:1px solid var(--border);border-radius:8px;padding:14px;display:flex;align-items:center;gap:12px">';
            h+='<span style="font-size:20px">'+s.icon+'</span>';
            h+='<div style="flex:1"><div style="display:flex;justify-content:space-between;align-items:center"><span style="color:var(--text-secondary);font-weight:600">'+s.name+'</span>';
            h+='<span style="color:'+color+';font-size:11px">'+dot+' '+s.status+'</span></div>';
            if(s.mem_mb||s.cpu){h+='<div style="color:var(--text-dim);font-size:11px;margin-top:4px">';
            if(s.mem_mb)h+=s.mem_mb;
            if(s.mem_mb&&s.cpu)h+=' · ';
            if(s.cpu)h+='CPU '+s.cpu;
            if(s.pid)h+=' · PID '+s.pid;
            h+='</div>'}
            h+='</div></div>';
        });
        h+='</div>';
        el.innerHTML=h;
    }catch(e){el.textContent='Failed to load services'}
}
if(document.getElementById('services-list')){loadServices();setInterval(loadServices,10000)}
if(document.getElementById('cot-db-size')){refreshCotSize();}
async function refreshCotSize(){var el=document.getElementById('cot-db-size');if(!el)return;el.textContent='...';el.style.color='';try{var r=await fetch('/api/takserver/cot-db-size');var d=await r.json();if(d.error){el.textContent=d.error;}else{el.textContent=d.size_human||'-';var b=d.size_bytes;if(typeof b==='number'){var gb25=25*1024*1024*1024;var gb40=40*1024*1024*1024;if(b<gb25)el.style.color='var(--green)';else if(b<gb40)el.style.color='var(--yellow)';else el.style.color='var(--red)';}}}catch(e){el.textContent='Error';}}
async function runVacuum(full){var msg=document.getElementById('vacuum-msg');var out=document.getElementById('vacuum-output');var btnA=document.getElementById('vacuum-analyze-btn');var btnF=document.getElementById('vacuum-full-btn');if(full&&!confirm("VACUUM FULL locks the CoT tables. Run when TAK Server is not running. Continue?"))return;if(msg){msg.textContent=full?'Running VACUUM FULL (may take a long time)...':'Running VACUUM ANALYZE...';msg.style.color='var(--text-dim)';}if(out){out.style.display='none';out.textContent='';}if(btnA){btnA.disabled=true;}if(btnF){btnF.disabled=true;}try{var r=await fetch('/api/takserver/vacuum',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({full:full})});var d=await r.json();if(d.success){if(msg){msg.textContent='Done.';msg.style.color='var(--green)';}if(out&&d.output){out.textContent=d.output;out.style.display='block';}if(document.getElementById('cot-db-size')){refreshCotSize();}}else{if(msg){msg.textContent=d.error||'Failed';msg.style.color='var(--red)';}if(out&&d.error){out.textContent=d.error;out.style.display='block';}}}catch(e){if(msg){msg.textContent='Error: '+e.message;msg.style.color='var(--red)';}}if(btnA){btnA.disabled=false;}if(btnF){btnF.disabled=false;}}

var serverLogOffset=0;
async function pollServerLog(){
    var el=document.getElementById('server-log');
    if(!el)return;
    try{
        var r=await fetch('/api/takserver/log?offset='+serverLogOffset+'&lines=80');
        var d=await r.json();
        if(d.entries&&d.entries.length>0){
            if(serverLogOffset===0)el.textContent='';
            d.entries.forEach(function(e){
                var l=document.createElement('div');
                if(e.indexOf('ERROR')>=0||e.indexOf('SEVERE')>=0)l.style.color='var(--red)';
                else if(e.indexOf('WARN')>=0)l.style.color='var(--yellow)';
                else if(e.indexOf('INFO')>=0)l.style.color='var(--text-secondary)';
                l.textContent=e;
                el.appendChild(l);
            });
            el.scrollTop=el.scrollHeight;
        }else if(serverLogOffset===0){
            el.textContent='No log entries yet. TAK Server may still be starting...';
        }
        serverLogOffset=d.offset||serverLogOffset;
    }catch(e){}
}
if(document.getElementById('server-log')){pollServerLog();setInterval(pollServerLog,5000)}

async function takControl(action){
    const btns=document.querySelectorAll('.control-btn');
    btns.forEach(b=>{b.disabled=true;b.style.opacity='0.5'});
    try{
        await fetch('/api/takserver/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});
        if(action==='start'||action==='restart'){
            sessionStorage.setItem('tak_just_started','1');
        }
        window.location.reload();
    }
    catch(e){alert('Failed: '+e.message);btns.forEach(b=>{b.disabled=false;b.style.opacity='1'})}
}

async function connectLdap(){
    var btn=document.getElementById('connect-ldap-btn');
    var msg=document.getElementById('connect-ldap-msg');
    if(btn){btn.disabled=true;btn.textContent='Connecting...';btn.style.opacity='0.7';}
    if(msg){msg.textContent='';msg.style.color='var(--text-secondary)';}
    try{
        var r=await fetch('/api/takserver/connect-ldap',{method:'POST',headers:{'Content-Type':'application/json'}});
        var d=await r.json();
        if(d.success){if(msg){msg.textContent=d.message||'Done.';msg.style.color='var(--green)';} alert(d.message||'LDAP connected. TAK Server restarted.');setTimeout(function(){window.location.reload();},500);}
        else{if(msg){msg.textContent=d.message||'Failed';msg.style.color='var(--red)';} if(btn){btn.disabled=false;btn.textContent='Connect TAK Server to LDAP';btn.style.opacity='1';}}
    }
    catch(e){if(msg){msg.textContent='Error: '+e.message;msg.style.color='var(--red)';} if(btn){btn.disabled=false;btn.textContent='Connect TAK Server to LDAP';btn.style.opacity='1';}}
}

(function(){
    if(sessionStorage.getItem('tak_just_started')==='1'){
        sessionStorage.removeItem('tak_just_started');
        var notice=document.createElement('div');
        notice.style.cssText='background:rgba(59,130,246,0.1);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:20px;text-align:center;font-family:JetBrains Mono,monospace;font-size:13px;color:#06b6d4;transition:opacity 1s';
        notice.textContent='\u23f3 TAK Server needs ~5 minutes to fully initialize before WebGUI login will work.';
        var main=document.querySelector('main');
        var banner=document.getElementById('status-banner');
        if(banner&&banner.nextSibling)main.insertBefore(notice,banner.nextSibling);
        else if(main)main.appendChild(notice);
        setTimeout(function(){notice.style.opacity='0';setTimeout(function(){notice.remove()},1000)},30000);
    }
})();

(function(){
    if(document.getElementById('upload-area')){
        fetch('/api/upload/takserver/existing').then(r=>r.json()).then(d=>{
            if(d.package||d.gpg_key||d.policy){
                if(d.package)uploadedFiles.package=d.package;
                if(d.gpg_key)uploadedFiles.gpg_key=d.gpg_key;
                if(d.policy)uploadedFiles.policy=d.policy;
                var pa=document.getElementById('progress-area');
                if(d.package){pa.insertAdjacentHTML('beforeend','<div class="progress-item"><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-family:JetBrains Mono,monospace;font-size:13px;color:var(--text-secondary)">'+d.package.filename+' ('+d.package.size_mb+' MB)</span><span style="font-family:JetBrains Mono,monospace;font-size:12px;color:var(--green)">\u2713 uploaded</span></div><div class="progress-bar-outer"><div class="progress-bar-inner" style="width:100%;background:var(--green)"></div></div></div>')}
                if(d.gpg_key){pa.insertAdjacentHTML('beforeend','<div class="progress-item"><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-family:JetBrains Mono,monospace;font-size:13px;color:var(--text-secondary)">'+d.gpg_key.filename+'</span><span style="font-family:JetBrains Mono,monospace;font-size:12px;color:var(--green)">\u2713 uploaded</span></div><div class="progress-bar-outer"><div class="progress-bar-inner" style="width:100%;background:var(--green)"></div></div></div>')}
                if(d.policy){pa.insertAdjacentHTML('beforeend','<div class="progress-item"><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-family:JetBrains Mono,monospace;font-size:13px;color:var(--text-secondary)">'+d.policy.filename+'</span><span style="font-family:JetBrains Mono,monospace;font-size:12px;color:var(--green)">\u2713 uploaded</span></div><div class="progress-bar-outer"><div class="progress-bar-inner" style="width:100%;background:var(--green)"></div></div></div>')}
                var a=document.getElementById('upload-area');if(a){a.style.maxHeight='120px';a.style.padding='20px';var ic=a.querySelector('.upload-icon');if(ic)ic.style.display='none'}
                updateUploadSummary();
            }
        }).catch(function(){});
    }
})();

async function takUninstall(){
    document.getElementById('tak-uninstall-modal').classList.add('open');
}
async function doUninstallTak(){
    var pw=document.getElementById('tak-uninstall-password').value;
    if(!pw){document.getElementById('tak-uninstall-msg').textContent='Please enter your password';return;}
    var msgEl=document.getElementById('tak-uninstall-msg');
    var progressEl=document.getElementById('tak-uninstall-progress');
    var cancelBtn=document.getElementById('tak-uninstall-cancel');
    var confirmBtn=document.getElementById('tak-uninstall-confirm');
    msgEl.textContent='';
    progressEl.style.display='flex';
    progressEl.innerHTML='<span class="uninstall-spinner"></span><span>Uninstalling...</span>';
    confirmBtn.disabled=true;
    cancelBtn.disabled=true;
    try{
        var r=await fetch('/api/takserver/uninstall',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
        var d=await r.json();
        if(d.success){
            progressEl.innerHTML='<span class="uninstall-spinner"></span><span>Done. Reloading...</span>';
            setTimeout(function(){window.location.href='/takserver';},800);
        }else{
            msgEl.textContent=d.error||'Uninstall failed';
            progressEl.style.display='none';
            progressEl.innerHTML='';
            confirmBtn.disabled=false;
            cancelBtn.disabled=false;
        }
    }catch(e){
        msgEl.textContent='Request failed: '+e.message;
        progressEl.style.display='none';
        progressEl.innerHTML='';
        confirmBtn.disabled=false;
        cancelBtn.disabled=false;
    }
}

async function cancelDeploy(){
    if(!confirm('Cancel the deployment? You can redeploy after.'))return;
    try{const r=await fetch('/api/deploy/cancel',{method:'POST',headers:{'Content-Type':'application/json'}});const d=await r.json();if(d.success){window.location.href='/takserver'}else{alert('Error: '+(d.error||'Unknown'))}}
    catch(e){alert('Failed: '+e.message)}
}

let uploadedFiles={package:null,gpg_key:null,policy:null};
let uploadsInProgress=0;

function handleDragOver(e){e.preventDefault();document.getElementById('upload-area').classList.add('dragover')}
function handleDragLeave(e){document.getElementById('upload-area').classList.remove('dragover')}
function handleDrop(e){e.preventDefault();document.getElementById('upload-area').classList.remove('dragover');queueFiles(e.dataTransfer.files)}
function handleFileSelect(e){queueFiles(e.target.files);e.target.value=''}
function handleAddMore(e){queueFiles(e.target.files);e.target.value=''}

function formatSize(b){if(b<1024)return b+' B';if(b<1024*1024)return(b/1024).toFixed(1)+' KB';if(b<1024*1024*1024)return(b/(1024*1024)).toFixed(1)+' MB';return(b/(1024*1024*1024)).toFixed(2)+' GB'}

async function removeFile(fn,elId){
    try{await fetch('/api/upload/takserver/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:fn})})}catch(e){}
    var el=document.getElementById(elId);if(el)el.remove();
    if(uploadedFiles.package&&uploadedFiles.package.filename===fn)uploadedFiles.package=null;
    if(uploadedFiles.gpg_key&&uploadedFiles.gpg_key.filename===fn)uploadedFiles.gpg_key=null;
    if(uploadedFiles.policy&&uploadedFiles.policy.filename===fn)uploadedFiles.policy=null;
    updateUploadSummary();
}

function queueFiles(fl){
    const a=document.getElementById('upload-area');if(a){a.style.maxHeight='120px';a.style.padding='20px';const ic=a.querySelector('.upload-icon');if(ic)ic.style.display='none'}
    for(const f of fl){
        var isDupe=false;
        if(uploadedFiles.package&&uploadedFiles.package.filename===f.name)isDupe=true;
        if(uploadedFiles.gpg_key&&uploadedFiles.gpg_key.filename===f.name)isDupe=true;
        if(uploadedFiles.policy&&uploadedFiles.policy.filename===f.name)isDupe=true;
        if(isDupe){var pa=document.getElementById('progress-area');pa.insertAdjacentHTML('beforeend','<div class="progress-item" style="opacity:0.6"><span style="font-family:JetBrains Mono,monospace;font-size:13px;color:var(--yellow)">\u26a0 '+f.name+' already uploaded - skipped</span></div>');continue}
        uploadFile(f);
    }
}

function uploadFile(file){
    uploadsInProgress++;
    const pa=document.getElementById('progress-area');
    const id='u-'+Date.now()+'-'+Math.random().toString(36).substr(2,5);
    var row=document.createElement('div');row.className='progress-item';row.id=id;
    var top=document.createElement('div');top.style.cssText='display:flex;justify-content:space-between;align-items:center';
    var lbl=document.createElement('span');lbl.style.cssText='font-family:JetBrains Mono,monospace;font-size:13px;color:var(--text-secondary)';lbl.textContent=file.name+' ('+formatSize(file.size)+')';
    var right=document.createElement('span');right.style.cssText='display:flex;align-items:center;gap:8px';
    var pct=document.createElement('span');pct.id=id+'-pct';pct.style.cssText='font-family:JetBrains Mono,monospace;font-size:12px;color:var(--cyan)';pct.textContent='0%';
    var cancelBtn=document.createElement('span');cancelBtn.id=id+'-cancel';cancelBtn.textContent='\u2717';cancelBtn.style.cssText='color:var(--red);cursor:pointer;font-size:14px';cancelBtn.title='Cancel upload';
    right.appendChild(pct);right.appendChild(cancelBtn);top.appendChild(lbl);top.appendChild(right);
    var barOuter=document.createElement('div');barOuter.className='progress-bar-outer';
    var barInner=document.createElement('div');barInner.className='progress-bar-inner';barInner.id=id+'-bar';barInner.style.width='0%';
    barOuter.appendChild(barInner);row.appendChild(top);row.appendChild(barOuter);pa.appendChild(row);
    const fd=new FormData();fd.append('files',file);
    const xhr=new XMLHttpRequest();
    window['xhr_'+id]=xhr;
    cancelBtn.onclick=function(){cancelUpload(id)};
    xhr.upload.onprogress=(e)=>{if(e.lengthComputable){const p=Math.round((e.loaded/e.total)*100);document.getElementById(id+'-bar').style.width=p+'%';document.getElementById(id+'-pct').textContent=p+'%'}};
    xhr.onload=()=>{
        delete window['xhr_'+id];
        const bar=document.getElementById(id+'-bar');const pc=document.getElementById(id+'-pct');bar.style.width='100%';
        var cb=document.getElementById(id+'-cancel');if(cb)cb.remove();
        if(xhr.status===200){const d=JSON.parse(xhr.responseText);bar.style.background='var(--green)';pc.style.color='var(--green)';if(d.package)uploadedFiles.package=d.package;if(d.gpg_key)uploadedFiles.gpg_key=d.gpg_key;if(d.policy)uploadedFiles.policy=d.policy;var rBtn=document.createElement('span');rBtn.textContent=' \u2717';rBtn.style.cssText='color:var(--red);cursor:pointer;margin-left:8px';rBtn.title='Remove';rBtn.onclick=function(ev){ev.stopPropagation();removeFile(file.name,id)};pc.textContent='\u2713 ';pc.appendChild(rBtn);updateUploadSummary()}
        else{bar.style.background='var(--red)';pc.textContent='\u2717';pc.style.color='var(--red)'}
        uploadsInProgress--;if(uploadsInProgress===0)updateUploadSummary()
    };
    xhr.onerror=()=>{delete window['xhr_'+id];document.getElementById(id+'-bar').style.background='var(--red)';document.getElementById(id+'-pct').textContent='\u2717';uploadsInProgress--;if(uploadsInProgress===0)updateUploadSummary()};
    xhr.onabort=()=>{delete window['xhr_'+id];uploadsInProgress--};
    xhr.ontimeout=()=>{delete window['xhr_'+id];document.getElementById(id+'-bar').style.background='var(--red)';document.getElementById(id+'-pct').textContent='Timeout';uploadsInProgress--;if(uploadsInProgress===0)updateUploadSummary()};
    xhr.timeout=1800000;
    xhr.open('POST','/api/upload/takserver');xhr.send(fd);
}

function cancelUpload(id){
    var xhr=window['xhr_'+id];
    if(xhr){xhr.abort();delete window['xhr_'+id]}
    var el=document.getElementById(id);if(el)el.remove();
}

function updateUploadSummary(){
    const r=document.getElementById('upload-results');const fl=document.getElementById('upload-files-list');r.style.display='block';
    let h='';
    if(uploadedFiles.package)h+='<div style="margin-bottom:8px">✓ <span style="color:var(--green)">'+uploadedFiles.package.filename+'</span> <span style="color:var(--text-dim)">('+uploadedFiles.package.size_mb+' MB)</span></div>';
    if(uploadedFiles.gpg_key)h+='<div style="margin-bottom:8px">✓ <span style="color:var(--green)">'+uploadedFiles.gpg_key.filename+'</span> <span style="color:var(--text-dim)">(GPG key)</span></div>';
    if(uploadedFiles.policy)h+='<div style="margin-bottom:8px">✓ <span style="color:var(--green)">'+uploadedFiles.policy.filename+'</span> <span style="color:var(--text-dim)">(policy)</span></div>';
    if(uploadedFiles.gpg_key&&uploadedFiles.policy)h+='<div style="margin-top:12px;color:var(--green)">🔐 GPG verification enabled</div>';
    else if(!uploadedFiles.gpg_key&&!uploadedFiles.policy)h+='<div style="margin-top:12px;color:var(--text-dim)">\u2139 No GPG key/policy - verification will be skipped</div>';
    else h+='<div style="margin-top:12px;color:var(--yellow)">\u26a0 Need both GPG key + policy for verification</div>';
    fl.innerHTML=h;
    if(uploadedFiles.package)document.getElementById('deploy-btn-area').style.display='block';
}

function showDeployConfig(){
    const ua=document.getElementById('upload-area');const pa=document.getElementById('progress-area');const ur=document.getElementById('upload-results');
    if(ua)ua.style.display='none';if(pa)pa.style.display='none';if(ur)ur.style.display='none';
    const main=document.querySelector('.main');
    main.querySelectorAll('.section-title').forEach(t=>{if(t.textContent.includes('Deploy'))t.remove()});
    const cd=document.createElement('div');
    cd.innerHTML=[
      '<div class="section-title">Configure Deployment</div>',
      '<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:28px;margin-bottom:20px">',
      '<div style="font-family:\'JetBrains Mono\',monospace;font-size:13px;color:var(--text-dim);margin-bottom:20px;text-transform:uppercase;letter-spacing:1px;font-weight:600">Certificate Information <span style="color:var(--red);font-size:10px;margin-left:8px">ALL FIELDS REQUIRED</span></div>',
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">',
      '<div class="form-field"><label>Country (2 letters)</label><input type="text" id="cert_country" placeholder="US" maxlength="2" style="text-transform:uppercase"></div>',
      '<div class="form-field"><label>State/Province</label><input type="text" id="cert_state" placeholder="CA" style="text-transform:uppercase"></div>',
      '<div class="form-field"><label>City</label><input type="text" id="cert_city" placeholder="SACRAMENTO" style="text-transform:uppercase"></div>',
      '<div class="form-field"><label>Organization</label><input type="text" id="cert_org" placeholder="MYAGENCY" style="text-transform:uppercase"></div>',
      '<div class="form-field"><label>Organizational Unit</label><input type="text" id="cert_ou" placeholder="IT" style="text-transform:uppercase"></div>',
      '</div>',
      '<div style="font-family:\'JetBrains Mono\',monospace;font-size:13px;color:var(--text-dim);margin:24px 0 20px;text-transform:uppercase;letter-spacing:1px;font-weight:600">Certificate Authority Names</div>',
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">',
      '<div class="form-field"><label>Root CA Name</label><input type="text" id="root_ca_name" placeholder="ROOT-CA-01" style="text-transform:uppercase"></div>',
      '<div class="form-field"><label>Intermediate CA Name</label><input type="text" id="intermediate_ca_name" placeholder="INTERMEDIATE-CA-01" style="text-transform:uppercase"></div>',
      '</div>',
      '<div style="font-family:\'JetBrains Mono\',monospace;font-size:13px;color:var(--text-dim);margin:24px 0 20px;text-transform:uppercase;letter-spacing:1px;font-weight:600">WebTAK Options (Port 8446)</div>',
      '<div style="display:flex;flex-direction:column;gap:14px">',
      '<label style="display:flex;align-items:center;gap:10px;color:var(--text-secondary);cursor:pointer;font-size:14px"><input type="checkbox" id="enable_admin_ui" onchange="toggleWebadminPassword()" style="width:18px;height:18px;accent-color:var(--accent)"> Enable Admin UI <span style="color:var(--text-dim);font-size:12px">- Browser admin (no cert needed)</span></label>',
      '<label style="display:flex;align-items:center;gap:10px;color:var(--text-secondary);cursor:pointer;font-size:14px"><input type="checkbox" id="enable_webtak" style="width:18px;height:18px;accent-color:var(--accent)"> Enable WebTAK <span style="color:var(--text-dim);font-size:12px">- Browser-based TAK client</span></label>',
      '<label style="display:flex;align-items:center;gap:10px;color:var(--text-secondary);cursor:pointer;font-size:14px"><input type="checkbox" id="enable_nonadmin_ui" style="width:18px;height:18px;accent-color:var(--accent)"> Enable Non-Admin UI <span style="color:var(--text-dim);font-size:12px">- Non-admin management</span></label>',
      '</div>',
      '<div id="webadmin-password-area" style="display:none;margin-top:20px;background:rgba(59,130,246,0.05);border:1px solid var(--border);border-radius:10px;padding:18px">',
      '<div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;color:var(--text-dim);margin-bottom:12px">Set a password for <span style="color:var(--cyan)">webadmin</span> user on port 8446</div>',
      '<div class="form-field" style="margin-bottom:12px"><label>WebAdmin Password</label><div style="position:relative"><input type="password" id="webadmin_password" placeholder="Min 15 chars: upper, lower, number, special"><button type="button" onclick="toggleShowPassword()" id="pw-toggle" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:13px;font-family:JetBrains Mono,monospace">show</button></div></div>',
      '<div class="form-field" style="margin-bottom:12px"><label>Confirm Password</label><input type="password" id="webadmin_password_confirm" placeholder="Re-enter password"></div>',
      '<div id="password-match" style="font-family:\'JetBrains Mono\',monospace;font-size:12px;margin-bottom:8px"></div>',
      '<div style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:var(--text-dim)">15+ characters, 1 uppercase, 1 lowercase, 1 number, 1 special character</div>',
      '<div id="password-validation" style="font-family:\'JetBrains Mono\',monospace;font-size:12px;margin-top:8px"></div>',
      '</div>',
      '<div style="margin-top:28px;text-align:center"><button onclick="startDeploy()" id="deploy-btn" style="padding:14px 48px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:10px;font-family:\'DM Sans\',sans-serif;font-size:16px;font-weight:600;cursor:pointer">\uD83D\uDE80 Deploy TAK Server</button></div>',
      '</div>',
      '<div id="deploy-log-area" style="display:none"><div class="section-title">Deployment Log</div><div id="deploy-log" style="background:#0c0f1a;border:1px solid var(--border);border-radius:12px;padding:20px;font-family:\'JetBrains Mono\',monospace;font-size:12px;color:var(--text-secondary);max-height:500px;overflow-y:auto;line-height:1.7;white-space:pre-wrap"></div></div>',
      '<div id="cert-download-area" style="display:none;margin-top:20px"><div class="section-title">Download Certificates</div><div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px"><div class="cert-downloads"><a href="/api/download/admin-cert" class="cert-btn cert-btn-secondary">\u2B07 admin.p12</a><a href="/api/download/user-cert" class="cert-btn cert-btn-secondary">\u2B07 user.p12</a><a href="/api/download/truststore" class="cert-btn cert-btn-secondary">\u2B07 truststore.p12</a></div><div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;color:var(--text-dim);margin-top:12px">Certificate password: <span style="color:var(--cyan)">atakatak</span></div></div></div>'
    ].join('');
    main.appendChild(cd);
    const pi=document.getElementById('webadmin_password');if(pi){pi.addEventListener('input',validatePassword);pi.addEventListener('input',checkPasswordMatch)}const pc=document.getElementById('webadmin_password_confirm');if(pc)pc.addEventListener('input',checkPasswordMatch);
}

function toggleWebadminPassword(){const a=document.getElementById('webadmin-password-area');if(a)a.style.display=document.getElementById('enable_admin_ui').checked?'block':'none'}

function toggleShowPassword(){const p=document.getElementById('webadmin_password');const c=document.getElementById('webadmin_password_confirm');const b=document.getElementById('pw-toggle');if(p.type==='password'){p.type='text';c.type='text';b.textContent='hide'}else{p.type='password';c.type='password';b.textContent='show'}}

function checkPasswordMatch(){const p=document.getElementById('webadmin_password').value;const c=document.getElementById('webadmin_password_confirm').value;const el=document.getElementById('password-match');if(!c){el.innerHTML='';return}if(p===c)el.innerHTML='<span style="color:var(--green)">\u2713 Passwords match</span>';else el.innerHTML='<span style="color:var(--red)">\u2717 Passwords do not match</span>'}

function validatePassword(){
    const p=document.getElementById('webadmin_password').value;const el=document.getElementById('password-validation');
    if(!p){el.innerHTML='';return false}
    const c=[{t:p.length>=15,l:'15+ chars'},{t:/[A-Z]/.test(p),l:'1 upper'},{t:/[a-z]/.test(p),l:'1 lower'},{t:/[0-9]/.test(p),l:'1 number'},{t:/[-_!@#$%^&*(){}+=~|:;<>,./\\?]/.test(p),l:'1 special'}];
    var h='';c.forEach(function(x){h+='<span style="color:'+(x.t?'var(--green)':'var(--red)')+';">'+(x.t?'\u2713':'\u2717')+' '+x.l+'</span> &nbsp; '});
    el.innerHTML=h;
    return c.every(function(x){return x.t});
}

async function startDeploy(){
    const rf=[{id:'cert_country',l:'Country'},{id:'cert_state',l:'State'},{id:'cert_city',l:'City'},{id:'cert_org',l:'Organization'},{id:'cert_ou',l:'Org Unit'},{id:'root_ca_name',l:'Root CA'},{id:'intermediate_ca_name',l:'Intermediate CA'}];
    const empty=rf.filter(f=>!document.getElementById(f.id).value.trim());
    if(empty.length>0){alert('Please fill in: '+empty.map(f=>f.l).join(', '));empty.forEach(f=>{const el=document.getElementById(f.id);el.style.borderColor='var(--red)';el.addEventListener('input',()=>el.style.borderColor='',{once:true})});return}
    const aui=document.getElementById('enable_admin_ui').checked;
    if(aui){const p=document.getElementById('webadmin_password').value;const pc=document.getElementById('webadmin_password_confirm').value;if(!p){alert('Please set a webadmin password.');return}if(p!==pc){alert('Passwords do not match.');return}if(!validatePassword()){alert('Password does not meet requirements.');return}}
    const btn=document.getElementById('deploy-btn');btn.disabled=true;btn.textContent='Deploying...';btn.style.opacity='0.6';btn.style.cursor='not-allowed';
    document.querySelectorAll('.form-field input,input[type="checkbox"]').forEach(el=>el.disabled=true);
    const cfg={cert_country:document.getElementById('cert_country').value.toUpperCase(),cert_state:document.getElementById('cert_state').value.toUpperCase(),cert_city:document.getElementById('cert_city').value.toUpperCase(),cert_org:document.getElementById('cert_org').value.toUpperCase(),cert_ou:document.getElementById('cert_ou').value.toUpperCase(),root_ca_name:document.getElementById('root_ca_name').value.toUpperCase(),intermediate_ca_name:document.getElementById('intermediate_ca_name').value.toUpperCase(),enable_admin_ui:document.getElementById('enable_admin_ui').checked,enable_webtak:document.getElementById('enable_webtak').checked,enable_nonadmin_ui:document.getElementById('enable_nonadmin_ui').checked,webadmin_password:aui?document.getElementById('webadmin_password').value:''};
    document.getElementById('deploy-log-area').style.display='block';
    try{const r=await fetch('/api/deploy/takserver',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});const d=await r.json();if(d.success)pollDeployLog();else{document.getElementById('deploy-log').textContent='✗ '+d.error;btn.disabled=false;btn.textContent='🚀 Deploy TAK Server';btn.style.opacity='1';btn.style.cursor='pointer'}}
    catch(e){document.getElementById('deploy-log').textContent='✗ '+e.message}
}

let logIndex=0,pollFails=0,logCleared=false;
function pollDeployLog(){
    const el=document.getElementById('deploy-log');
    const poll=async()=>{
        try{const r=await fetch('/api/deploy/log?after='+logIndex);const d=await r.json();pollFails=0;
            if(!logCleared&&d.entries.length>0){el.textContent='';logCleared=true}
            if(d.entries.length>0){d.entries.forEach(e=>{var isTimer=e.trim().charAt(0)=='\u23f3'&&e.indexOf(':')>0;if(isTimer){var prev=el.querySelector('[data-timer]');if(prev){prev.textContent=e;logIndex=d.total;return}};if(!isTimer){var old=el.querySelector('[data-timer]');if(old)old.removeAttribute('data-timer')};var l=document.createElement('div');if(isTimer)l.setAttribute('data-timer','1');if(e.indexOf('\u2713')>=0)l.style.color='var(--green)';else if(e.indexOf('\u2717')>=0||e.indexOf('FATAL')>=0)l.style.color='var(--red)';else if(e.indexOf('\u2501\u2501\u2501')>=0)l.style.color='var(--cyan)';else if(e.indexOf('\u26a0')>=0)l.style.color='var(--yellow)';else if(e.indexOf('===')>=0||e.indexOf('WebGUI')>=0||e.indexOf('Username')>=0)l.style.color='var(--green)';l.textContent=e;el.appendChild(l)});logIndex=d.total;el.scrollTop=el.scrollHeight}
            if(d.running)setTimeout(poll,1000);
            else if(d.complete){const b=document.getElementById('deploy-btn');if(b){b.textContent='\u2713 Deployment Complete';b.style.background='var(--green)';b.style.opacity='1'};const dl=document.getElementById('cert-download-area');if(dl)dl.style.display='block';var wa=document.createElement('div');wa.style.cssText='background:rgba(59,130,246,0.1);border:1px solid var(--border);border-radius:10px;padding:20px;margin-top:20px;text-align:center';var wt=document.createElement('div');wt.style.cssText='font-family:JetBrains Mono,monospace;font-size:14px;color:#06b6d4;margin-bottom:12px';wt.textContent='\u23f3 TAK Server needs ~5 minutes to fully initialize before login will work.';var wb=document.createElement('button');wb.textContent='Refresh Page';wb.style.cssText='padding:10px 24px;background:linear-gradient(135deg,#1e40af,#0e7490);color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer';wb.onclick=function(){window.location.href='/takserver'};wa.appendChild(wt);wa.appendChild(wb);document.getElementById('deploy-log-area').after(wa)}
            else if(d.error){const b=document.getElementById('deploy-btn');if(b){b.textContent='\u2717 Deployment Failed';b.style.background='var(--red)';b.style.opacity='1'}}
        }catch(e){pollFails++;if(pollFails<30)setTimeout(poll,2000)}
    };poll();
}
var upgradeLogIndex=0;
function uploadUpgradeDeb(file){
  if(!file||!file.name.toLowerCase().endsWith('.deb')){var m=document.getElementById('tak-update-msg');if(m){m.textContent='Select a .deb file.';m.style.color='var(--red)';}return;}
  var fd=new FormData();fd.append('files',file);
  var fnEl=document.getElementById('upgrade-filename');if(fnEl){fnEl.textContent='Uploading '+file.name+'...';fnEl.style.display='block';}
  fetch('/api/upload/takserver',{method:'POST',body:fd,credentials:'same-origin'}).then(function(r){return r.json();}).then(function(d){
    if(d.error){if(fnEl)fnEl.textContent=d.error;return;}
    if(fnEl)fnEl.textContent='Ready: '+file.name;
    var m=document.getElementById('tak-update-msg');if(m)m.textContent='';
  }).catch(function(e){if(fnEl)fnEl.textContent='Upload failed';var m=document.getElementById('tak-update-msg');if(m){m.textContent=e.message;m.style.color='var(--red)';}});
}
function handleUpgradeFile(ev){var f=ev.target.files[0];if(f)uploadUpgradeDeb(f);}
function handleUpgradeDrop(ev){ev.preventDefault();ev.stopPropagation();document.getElementById('upgrade-upload-area').classList.remove('dragover');var f=ev.dataTransfer.files[0];if(f)uploadUpgradeDeb(f);}
function takToggleUpdate(){var body=document.getElementById('tak-update-body');var btn=document.getElementById('tak-update-toggle-btn');var icon=document.getElementById('tak-update-toggle-icon');var label=document.getElementById('tak-update-toggle-label');if(!body)return;var show=body.style.display==='none';body.style.display=show?'block':'none';if(icon)icon.textContent=show?'\u9650':'\u9660';if(label)label.textContent=show?'Collapse':'Expand';}
async function startTakUpdate(){
  var btn=document.getElementById('tak-update-btn');var msg=document.getElementById('tak-update-msg');
  if(btn)btn.disabled=true;if(msg){msg.textContent='Starting update...';msg.style.color='var(--text-dim)';}
  try{
    var r=await fetch('/api/takserver/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({}),credentials:'same-origin'});
    var d=await r.json();
    if(d.error){if(msg){msg.textContent=d.error;msg.style.color='var(--red)';}if(btn)btn.disabled=false;return;}
    var wrap=document.getElementById('upgrade-log-wrap');if(wrap)wrap.style.display='block';
    var el=document.getElementById('upgrade-log');if(el)el.textContent='Connecting...';
    upgradeLogIndex=0;pollUpgradeLog();
  }catch(e){if(msg){msg.textContent='Error: '+e.message;msg.style.color='var(--red)';}if(btn)btn.disabled=false;}
}
function pollUpgradeLog(){
  var el=document.getElementById('upgrade-log');
  if(!el)return;
  function poll(){
    fetch('/api/takserver/update/log?index='+upgradeLogIndex,{credentials:'same-origin'}).then(function(r){return r.json();}).then(function(d){
      if(d.entries&&d.entries.length){if(upgradeLogIndex===0)el.textContent='';el.textContent+=d.entries.join(String.fromCharCode(10))+String.fromCharCode(10);el.scrollTop=el.scrollHeight;upgradeLogIndex=d.total;}
      if(!d.running){var btn=document.getElementById('tak-update-btn');if(btn)btn.disabled=false;if(d.complete){if(btn)btn.textContent='Update complete';var m=document.getElementById('tak-update-msg');if(m)m.textContent='Done. Refreshing...';setTimeout(function(){location.reload();},2000);}else if(d.error){var m=document.getElementById('tak-update-msg');if(m){m.textContent='Update failed';m.style.color='var(--red)';}}}}else{setTimeout(poll,800);}
    });
  }
  poll();
}
if(document.body.getAttribute('data-tak-deploying')==='true' && document.getElementById('deploy-log')){ pollDeployLog(); }
if(document.body.getAttribute('data-tak-upgrading')==='true' && document.getElementById('upgrade-log')){ upgradeLogIndex=0; pollUpgradeLog(); }
