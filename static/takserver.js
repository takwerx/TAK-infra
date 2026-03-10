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
        if(d.success){if(msg){msg.textContent=d.message||'Synced.';msg.style.color='var(--green)';} if(btn){btn.disabled=false;btn.style.opacity='1';} loadWebadminSuperuserStatus();}
        else{if(msg){msg.textContent=d.error||d.message||'Failed';msg.style.color='var(--red)';} if(btn){btn.disabled=false;btn.style.opacity='1';}}
    }
    catch(e){if(msg){msg.textContent='Error: '+e.message;msg.style.color='var(--red)';} if(btn){btn.disabled=false;btn.style.opacity='1';}}
}

async function saveTakCertPassword(){
    var input=document.getElementById('tak-cert-password-input');
    var msg=document.getElementById('tak-cert-password-msg');
    if(!input||!msg)return;
    var pw=(input.value||'').trim();
    if(!pw){msg.textContent='Enter a password';msg.style.color='var(--red)';return;}
    msg.textContent='Saving...';msg.style.color='var(--text-dim)';
    try{
        var r=await fetch('/api/takserver/cert-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
        var d=await r.json();
        if(d.success){msg.textContent='Saved';msg.style.color='var(--green)';loadTakCertPassword();}
        else{msg.textContent=d.error||'Save failed';msg.style.color='var(--red)';}
    }catch(e){
        msg.textContent='Error: '+e.message;msg.style.color='var(--red)';
    }
}

async function loadTakCertPassword(){
    try{
        var r=await fetch('/api/takserver/cert-password');
        var d=await r.json();
        var pw=(d&&d.password)||'atakatak';
        var inline=document.getElementById('tak-cert-password-inline');
        if(inline)inline.textContent=pw;
        var deployInline=document.getElementById('deploy-cert-password-inline');
        if(deployInline)deployInline.textContent=pw;
    }catch(e){}
}

async function loadWebadminSuperuserStatus(){
    var el=document.getElementById('webadmin-superuser-status');
    if(!el)return;
    try{
        var r=await fetch('/api/takserver/webadmin-authentik-status');
        var d=await r.json();
        if(!d.available){
            el.textContent='Unavailable';
            el.style.color='var(--text-dim)';
            return;
        }
        if(!d.exists){
            el.textContent='No';
            el.style.color='var(--red)';
            return;
        }
        el.textContent=d.is_superuser?'Yes':'No';
        el.style.color=d.is_superuser?'var(--green)':'var(--yellow)';
    }catch(e){
        el.textContent='Error';
        el.style.color='var(--red)';
    }
}
async function checkLdapDrift(){
    var banner=document.getElementById('ldap-drift-banner');
    var msg=document.getElementById('ldap-drift-msg');
    if(!banner||!msg)return;
    try{
        var r=await fetch('/api/takserver/ldap-drift-check');
        var d=await r.json();
        if(d.match===false){
            msg.textContent=d.detail||'LDAP credential mismatch — click Resync LDAP to fix.';
            banner.style.display='block';
        }else{banner.style.display='none';}
    }catch(e){banner.style.display='none';}
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
if(document.getElementById('webadmin-superuser-status')){loadWebadminSuperuserStatus();}
if(document.getElementById('tak-cert-password-inline')){loadTakCertPassword();}
if(document.getElementById('ldap-drift-banner')){checkLdapDrift();}
if(document.getElementById('cot-db-size')){refreshCotSize();}
if(document.getElementById('cert-expiry-info')){loadCertExpiry();}
if(document.getElementById('rotate-ca-info')){loadCAInfo();}
async function loadGroups(){
  var el=document.getElementById('cc-groups-list');if(!el)return;
  el.innerHTML='<span style="color:var(--text-dim)">Loading groups...</span>';
  try{
    var r=await fetch('/api/takserver/groups');var d=await r.json();
    if(d.error&&(!d.groups||!d.groups.length)){el.innerHTML='<span style="color:var(--red)">'+d.error+'</span> <button type="button" onclick="loadGroups()" style="margin-left:8px;padding:4px 12px;background:rgba(59,130,246,0.1);color:var(--accent);border:1px solid var(--border);border-radius:6px;font-size:11px;cursor:pointer">Retry</button>';return;}
    if(!d.groups||d.groups.length===0){el.innerHTML='<span style="color:var(--text-dim)">No groups found. Groups are created in the TAK Server WebGUI or via LDAP.</span>';return;}
    var h='<div style="display:grid;grid-template-columns:1fr auto auto auto;gap:4px 16px;align-items:center">';
    h+='<div style="color:var(--text-dim);font-size:11px;font-weight:600;padding-bottom:4px">GROUP</div>';
    h+='<div style="color:var(--text-dim);font-size:11px;font-weight:600;text-align:center;padding-bottom:4px">READ</div>';
    h+='<div style="color:var(--text-dim);font-size:11px;font-weight:600;text-align:center;padding-bottom:4px">WRITE</div>';
    h+='<div style="color:var(--text-dim);font-size:11px;font-weight:600;text-align:center;padding-bottom:4px">BOTH</div>';
    for(var i=0;i<d.groups.length;i++){
      var g=d.groups[i],n=g.name,safe=n.replace(/"/g,'&quot;');
      h+='<div style="color:var(--text-secondary);padding:4px 0">'+n+'</div>';
      h+='<div style="text-align:center"><input type="checkbox" class="cc-grp-read" data-group="'+safe+'" style="width:16px;height:16px;accent-color:var(--cyan)" onchange="ccGroupChanged(this,\'read\')"></div>';
      h+='<div style="text-align:center"><input type="checkbox" class="cc-grp-write" data-group="'+safe+'" style="width:16px;height:16px;accent-color:var(--cyan)" onchange="ccGroupChanged(this,\'write\')"></div>';
      h+='<div style="text-align:center"><input type="checkbox" class="cc-grp-both" data-group="'+safe+'" style="width:16px;height:16px;accent-color:var(--accent)" onchange="ccGroupChanged(this,\'both\')"></div>';
    }
    h+='</div>';
    el.innerHTML=h;
  }catch(e){el.textContent='Failed to load groups';}
}
function ccGroupChanged(cb,type){
  var grp=cb.getAttribute('data-group');
  var r=document.querySelector('.cc-grp-read[data-group="'+grp+'"]');
  var w=document.querySelector('.cc-grp-write[data-group="'+grp+'"]');
  var b=document.querySelector('.cc-grp-both[data-group="'+grp+'"]');
  if(type==='both'){
    if(cb.checked){r.checked=true;w.checked=true;}else{r.checked=false;w.checked=false;}
  }else{
    b.checked=(r.checked&&w.checked);
  }
}
async function createClientCert(){
  var nameEl=document.getElementById('cc-name');
  var btn=document.getElementById('cc-create-btn');
  var msg=document.getElementById('cc-msg');
  var result=document.getElementById('cc-result');
  var name=(nameEl?nameEl.value:'').trim();
  if(!name){if(msg){msg.textContent='Enter a client name.';msg.style.color='var(--red)';}return;}
  var groupsIn=[],groupsOut=[];
  document.querySelectorAll('.cc-grp-read:checked').forEach(function(c){var g=c.getAttribute('data-group');if(groupsOut.indexOf(g)<0)groupsOut.push(g);});
  document.querySelectorAll('.cc-grp-write:checked').forEach(function(c){var g=c.getAttribute('data-group');if(groupsIn.indexOf(g)<0)groupsIn.push(g);});
  if(groupsIn.length===0&&groupsOut.length===0){if(msg){msg.textContent='Select at least one group with read or write permission.';msg.style.color='var(--red)';}return;}
  if(btn)btn.disabled=true;
  if(msg){msg.textContent='Creating certificate...';msg.style.color='var(--text-dim)';}
  if(result)result.style.display='none';
  try{
    var r=await fetch('/api/takserver/create-client-cert',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name,groups_in:groupsIn,groups_out:groupsOut})});
    var d=await r.json();
    if(d.error){if(msg){msg.textContent=d.error;msg.style.color='var(--red)';}if(btn)btn.disabled=false;return;}
    if(msg){msg.textContent='';msg.style.color='var(--text-dim)';}
    if(result){
      result.style.display='block';
      document.getElementById('cc-result-name').textContent=d.name+'.p12';
      document.getElementById('cc-download-link').href=d.download_url;
    }
    if(btn)btn.disabled=false;
    if(nameEl)nameEl.value='';
  }catch(e){if(msg){msg.textContent='Error: '+e.message;msg.style.color='var(--red)';}if(btn)btn.disabled=false;}
}
async function loadCertExpiry(){
  var el=document.getElementById('cert-expiry-info');if(!el)return;
  try{
    var r=await fetch('/api/takserver/cert-expiry');var d=await r.json();
    var h='';
    var certs=[['root_ca','Root CA'],['intermediate_ca','Intermediate CA']];
    for(var i=0;i<certs.length;i++){
      var key=certs[i][0],label=certs[i][1],c=d[key];
      if(!c)continue;
      if(c.error){h+='<div style="margin-bottom:6px"><span style="color:var(--text-secondary)">'+label+'</span> <span style="color:var(--text-dim)">'+c.error+'</span></div>';continue;}
      var days=c.days_left,color='var(--green)';
      if(days<=90)color='var(--red)';else if(days<=365)color='var(--yellow)';
      var yrs=Math.floor(days/365),rem=days%365,mo=Math.floor(rem/30),dd=rem%30;
      var parts=[];if(yrs>0)parts.push(yrs+'y');if(mo>0)parts.push(mo+'mo');if(dd>0||parts.length===0)parts.push(dd+'d');
      h+='<div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">';
      h+='<span style="color:var(--text-secondary);min-width:130px">'+label+'</span>';
      h+='<span style="color:'+color+';font-weight:600">'+parts.join(' ')+'</span>';
      h+='<span style="color:var(--text-dim)">'+c.expires+'</span>';
      h+='</div>';
    }
    el.innerHTML=h||'No certificates found.';
    var banner=document.getElementById('cert-expiry-banner');
    if(banner){
      var bh='';
      for(var j=0;j<certs.length;j++){
        var bk=certs[j][0],bl=certs[j][1],bc=d[bk];
        if(!bc||bc.error)continue;
        var bd=bc.days_left,bcolor='var(--green)';
        if(bd<=90)bcolor='var(--red)';else if(bd<=365)bcolor='var(--yellow)';
        var byrs=Math.floor(bd/365),brem=bd%365,bmo=Math.floor(brem/30),bdd=brem%30;
        var bp=[];if(byrs>0)bp.push(byrs+'y');if(bmo>0)bp.push(bmo+'mo');if(bdd>0||bp.length===0)bp.push(bdd+'d');
        if(bh)bh+='<br>';
        bh+=bl+' <span style="color:'+bcolor+';font-weight:600">'+bp.join(' ')+'</span>';
      }
      banner.innerHTML=bh;
    }
  }catch(e){el.textContent='Failed to load certificate info';}
}

async function loadCAInfo(){
  var infoEl=document.getElementById('rotate-ca-info');
  var ctrlEl=document.getElementById('rotate-ca-controls');
  var revokeEl=document.getElementById('revoke-ca-section');
  if(!infoEl)return;
  try{
    var r=await fetch('/api/takserver/ca-info');
    var d=await r.json();
    var h='';
    function fmtDays(days){
      var yrs=Math.floor(days/365),rem=days%365,mo=Math.floor(rem/30),dd=rem%30;
      var parts=[];if(yrs>0)parts.push(yrs+'y');if(mo>0)parts.push(mo+'mo');if(dd>0||parts.length===0)parts.push(dd+'d');
      return parts.join(' ');
    }
    if(d.root_ca){
      var rd=d.root_ca.days_left,rc='var(--green)';
      if(rd!==null){if(rd<=90)rc='var(--red)';else if(rd<=365)rc='var(--yellow)';}
      h+='<div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">';
      h+='<span style="color:var(--text-secondary);min-width:140px">Root CA</span>';
      h+='<span style="color:var(--cyan);font-weight:600">'+d.root_ca.name+'</span>';
      if(d.root_ca.expires&&rd!==null)h+='<span style="color:'+rc+';font-weight:600">'+fmtDays(rd)+'</span> <span style="color:var(--text-dim)">'+d.root_ca.expires+'</span>';
      h+='</div>';
    }
    if(d.intermediate_ca){
      var days=d.intermediate_ca.days_left,color='var(--green)';
      if(days!==null){if(days<=90)color='var(--red)';else if(days<=365)color='var(--yellow)';}
      h+='<div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">';
      h+='<span style="color:var(--text-secondary);min-width:140px">Intermediate CA</span>';
      h+='<span style="color:var(--cyan);font-weight:600">'+d.intermediate_ca.name+'</span>';
      if(d.intermediate_ca.expires&&days!==null)h+='<span style="color:'+color+';font-weight:600">'+fmtDays(days)+'</span> <span style="color:var(--text-dim)">'+d.intermediate_ca.expires+'</span>';
      h+='</div>';
    }
    if(d.truststore_file){
      h+='<div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">';
      h+='<span style="color:var(--text-secondary);min-width:140px">Truststore</span>';
      h+='<span style="color:var(--text-dim)">'+d.truststore_file+'</span>';
      if(d.truststore_aliases&&d.truststore_aliases.length){
        h+=' <span style="color:var(--text-dim)">('+d.truststore_aliases.join(', ')+')</span>';
      }
      h+='</div>';
    }
    infoEl.innerHTML=h||'No CA information available.';
    if(ctrlEl)ctrlEl.style.display='block';
    var nameInput=document.getElementById('rotate-ca-name');
    if(nameInput&&d.suggested_new_name&&!nameInput.value)nameInput.value=d.suggested_new_name;
    // Populate Root CA rotation card info (root CA only)
    var rootInfoEl=document.getElementById('rotate-root-info');
    if(rootInfoEl&&d.root_ca){
      var rh='<div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">';
      rh+='<span style="color:var(--text-secondary);min-width:140px">Root CA</span>';
      rh+='<span style="color:var(--cyan);font-weight:600">'+d.root_ca.name+'</span>';
      var rd2=d.root_ca.days_left,rc2='var(--green)';
      if(rd2!==null){if(rd2<=90)rc2='var(--red)';else if(rd2<=365)rc2='var(--yellow)';}
      if(d.root_ca.expires&&rd2!==null)rh+='<span style="color:'+rc2+';font-weight:600">'+fmtDays(rd2)+'</span> <span style="color:var(--text-dim)">'+d.root_ca.expires+'</span>';
      rh+='</div>';
      rootInfoEl.innerHTML=rh;
    }
    var rootNameInput=document.getElementById('rotate-root-name');
    if(rootNameInput&&d.suggested_new_root_name&&!rootNameInput.value)rootNameInput.value=d.suggested_new_root_name;
    var rootIntInput=document.getElementById('rotate-root-int-name');
    if(rootIntInput&&d.suggested_new_root_int_name&&!rootIntInput.value)rootIntInput.value=d.suggested_new_root_int_name;
    if(revokeEl&&d.old_cas_in_truststore&&d.old_cas_in_truststore.length>0){
      revokeEl.style.display='block';
      var listEl=document.getElementById('revoke-ca-list');
      if(listEl){
        var rh='';
        for(var i=0;i<d.old_cas_in_truststore.length;i++){
          var alias=d.old_cas_in_truststore[i];
          rh+='<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">';
          rh+='<span style="color:var(--yellow)">'+alias+'</span>';
          rh+='<button type="button" onclick="revokeOldCA(\''+alias.replace(/'/g,"\\'")+'\')" style="padding:6px 14px;background:rgba(239,68,68,0.15);color:var(--red);border:1px solid rgba(239,68,68,0.3);border-radius:6px;font-family:\'JetBrains Mono\',monospace;font-size:11px;cursor:pointer">Revoke</button>';
          rh+='</div>';
        }
        listEl.innerHTML=rh;
      }
    }
  }catch(e){infoEl.textContent='Failed to load CA info';}
}

async function rotateIntCA(){
  var nameInput=document.getElementById('rotate-ca-name');
  var newName=(nameInput?nameInput.value:'').trim();
  if(!newName){alert('Enter a name for the new Intermediate CA');return;}
  if(!confirm('This will create a new Intermediate CA "'+newName+'", regenerate server/admin/user certificates, and restart TAK Server. Existing clients will remain connected via the old CA in the truststore.\n\nContinue?'))return;
  var btn=document.getElementById('rotate-ca-btn');
  var msg=document.getElementById('rotate-ca-msg');
  var logEl=document.getElementById('rotate-ca-log');
  if(btn)btn.disabled=true;
  if(msg){msg.textContent='Starting rotation...';msg.style.color='var(--text-dim)';}
  if(logEl){logEl.style.display='block';logEl.textContent='Starting...\n';}
  try{
    var r=await fetch('/api/takserver/rotate-intca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({new_ca_name:newName})});
    var d=await r.json();
    if(d.error){
      if(msg){msg.textContent=d.error;msg.style.color='var(--red)';}
      if(btn)btn.disabled=false;
      return;
    }
    if(msg){msg.textContent='Rotation in progress...';}
    pollRotateLog();
  }catch(e){
    if(msg){msg.textContent='Error: '+e.message;msg.style.color='var(--red)';}
    if(btn)btn.disabled=false;
  }
}

function pollRotateLog(){
  var logEl=document.getElementById('rotate-ca-log');
  var msg=document.getElementById('rotate-ca-msg');
  var btn=document.getElementById('rotate-ca-btn');
  fetch('/api/takserver/rotate-intca/status').then(function(r){return r.json();}).then(function(d){
    if(logEl&&d.log){logEl.textContent=d.log.join('\n');logEl.scrollTop=logEl.scrollHeight;}
    if(!d.running&&d.complete){
      if(d.error){
        if(msg){msg.textContent='Rotation failed';msg.style.color='var(--red)';}
      }else{
        if(msg){msg.textContent='Rotation complete!';msg.style.color='var(--green)';}
      }
      if(btn)btn.disabled=false;
      loadCAInfo();
      loadCertExpiry();
    }else{
      setTimeout(pollRotateLog,1500);
    }
  }).catch(function(){setTimeout(pollRotateLog,2000);});
}

async function revokeOldCA(alias){
  if(!confirm('REVOKE "'+alias+'" from the truststore?\n\nAll clients with certificates signed by this CA will be DISCONNECTED and must re-enroll.\n\nThis cannot be undone.'))return;
  var msgEl=document.getElementById('revoke-ca-msg');
  if(msgEl){msgEl.textContent='Revoking '+alias+'...';msgEl.style.color='var(--text-dim)';}
  try{
    var r=await fetch('/api/takserver/revoke-old-ca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old_ca_alias:alias})});
    var d=await r.json();
    if(d.success){
      if(msgEl){msgEl.innerHTML='<span style="color:var(--green)">'+d.message+'</span>';}
      loadCAInfo();
    }else{
      if(msgEl){msgEl.innerHTML='<span style="color:var(--red)">'+(d.error||'Failed')+'</span>';}
    }
  }catch(e){
    if(msgEl){msgEl.innerHTML='<span style="color:var(--red)">Error: '+e.message+'</span>';}
  }
}

async function rotateRootCA(){
  var rootInput=document.getElementById('rotate-root-name');
  var intInput=document.getElementById('rotate-root-int-name');
  var newRoot=(rootInput?rootInput.value:'').trim();
  var newInt=(intInput?intInput.value:'').trim();
  if(!newRoot||!newInt){alert('Enter names for both the new Root CA and new Intermediate CA');return;}
  if(!confirm('⚠ FULL ROOT CA ROTATION ⚠\n\nThis will:\n• Create new Root CA: '+newRoot+'\n• Create new Intermediate CA: '+newInt+'\n• Regenerate ALL certificates\n• Restart TAK Server\n• Update TAK Portal\n\nALL existing client connections will be DISCONNECTED.\nUsers must re-enroll via TAK Portal QR code.\n\nAre you sure?'))return;
  if(!confirm('FINAL CONFIRMATION\n\nThis is a destructive operation. The old PKI will be removed.\n\nType your maintenance window: 0900 it goes dark, 0915 scan new QR.\n\nProceed?'))return;
  var btn=document.getElementById('rotate-root-btn');
  var msg=document.getElementById('rotate-root-msg');
  var logEl=document.getElementById('rotate-root-log');
  if(btn)btn.disabled=true;
  if(msg){msg.textContent='Starting Root CA rotation...';msg.style.color='var(--text-dim)';}
  if(logEl){logEl.style.display='block';logEl.textContent='Starting...\n';}
  try{
    var r=await fetch('/api/takserver/rotate-rootca',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({new_root_name:newRoot,new_int_name:newInt})});
    var d=await r.json();
    if(d.error){
      if(msg){msg.textContent=d.error;msg.style.color='var(--red)';}
      if(btn)btn.disabled=false;
      return;
    }
    if(msg){msg.textContent='Root CA rotation in progress...';}
    pollRootRotateLog();
  }catch(e){
    if(msg){msg.textContent='Error: '+e.message;msg.style.color='var(--red)';}
    if(btn)btn.disabled=false;
  }
}

function pollRootRotateLog(){
  var logEl=document.getElementById('rotate-root-log');
  var msg=document.getElementById('rotate-root-msg');
  var btn=document.getElementById('rotate-root-btn');
  fetch('/api/takserver/rotate-rootca/status').then(function(r){return r.json();}).then(function(d){
    if(logEl&&d.log){logEl.textContent=d.log.join('\n');logEl.scrollTop=logEl.scrollHeight;}
    if(!d.running&&d.complete){
      if(d.error){
        if(msg){msg.textContent='Root CA rotation failed';msg.style.color='var(--red)';}
      }else{
        if(msg){msg.textContent='Root CA rotation complete!';msg.style.color='var(--green)';}
      }
      if(btn)btn.disabled=false;
      loadCAInfo();
      loadCertExpiry();
    }else{
      setTimeout(pollRootRotateLog,1500);
    }
  }).catch(function(){setTimeout(pollRootRotateLog,2000);});
}

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

async function takControl(action, target){
    target = target || 'core';
    const btns=document.querySelectorAll('.control-btn');
    btns.forEach(b=>{b.disabled=true;b.style.opacity='0.5'});
    try{
        var r = await fetch('/api/takserver/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:action,target:target})});
        var d = await r.json();
        if(d.results && d.results.database && !d.results.database.success){
            alert('Database restart failed on ' + (d.results.database.host || 'Server One'));
        }
        if(action==='start'||action==='restart'){
            sessionStorage.setItem('tak_just_started','1');
        }
        window.location.reload();
    }
    catch(e){alert('Failed: '+e.message);btns.forEach(b=>{b.disabled=false;b.style.opacity='1'})}
}

async function syncTakDbPassword(){
    var btns=document.querySelectorAll('.control-btn');
    btns.forEach(b=>{b.disabled=true;b.style.opacity='0.5'});
    try{
        var pwEl=document.getElementById('sync-db-password-input');
        var pw=(pwEl&&pwEl.value)?pwEl.value.trim():'';
        var r=await fetch('/api/takserver/two-server/sync-db-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pw?{password:pw}:{})});
        var d=await r.json();
        if(d.success){alert(d.message||'DB password synced. TAK Server restarting — try 8443/8446 in a minute.');window.location.reload();}
        else{alert(d.error||'Sync failed');btns.forEach(b=>{b.disabled=false;b.style.opacity='1'});}
    }catch(e){alert('Failed: '+e.message);btns.forEach(b=>{b.disabled=false;b.style.opacity='1'});}
}

async function takUpdateConfig(){
    var btn=document.getElementById('tak-update-config-btn');
    if(!btn)return;
    if(btn.disabled)return;
    btn.disabled=true;
    btn.style.opacity='0.6';
    var origText=btn.textContent;
    btn.textContent='Updating...';
    try{
        var r=await fetch('/api/takserver/update-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
        var d=await r.json();
        if(d.error){
            alert(d.error);
            btn.disabled=false;
            btn.style.opacity='1';
            btn.textContent=origText;
            return;
        }
        btn.textContent='Update started...';
        function poll(){
            fetch('/api/takserver/update-config/status').then(function(res){return res.json();}).then(function(st){
                if(!st.running){
                    if(st.error){
                        alert('Update config failed: '+(st.message||'Unknown error'));
                    }else{
                        btn.textContent='Done — reloading';
                        setTimeout(function(){window.location.reload();},1500);
                        return;
                    }
                    btn.disabled=false;
                    btn.style.opacity='1';
                    btn.textContent=origText;
                }else{
                    setTimeout(poll,1500);
                }
            }).catch(function(){
                btn.disabled=false;
                btn.style.opacity='1';
                btn.textContent=origText;
            });
        }
        setTimeout(poll,2000);
    }catch(e){
        alert('Failed: '+e.message);
        btn.disabled=false;
        btn.style.opacity='1';
        btn.textContent=origText;
    }
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
        updateUploadHint();
        updateDeployModeFirstHint();
        var single=document.getElementById('dep_mode_single');
        var split=document.getElementById('dep_mode_split');
        if(single)single.addEventListener('change',function(){toggleTwoServerPanel();updateUploadHint();updateDeployModeFirstHint();});
        if(split)split.addEventListener('change',function(){toggleTwoServerPanel();updateUploadHint();updateDeployModeFirstHint();});
        fetch('/api/upload/takserver/existing').then(r=>r.json()).then(d=>{
            var hasAny=(d.packages&&d.packages.length)||d.gpg_key||d.policy;
            if(hasAny){
                if(d.packages)uploadedFiles.packages=d.packages.slice();
                if(d.gpg_key)uploadedFiles.gpg_key=d.gpg_key;
                if(d.policy)uploadedFiles.policy=d.policy;
                var pa=document.getElementById('progress-area');
                (d.packages||[]).forEach(function(p){pa.insertAdjacentHTML('beforeend','<div class="progress-item"><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-family:JetBrains Mono,monospace;font-size:13px;color:var(--text-secondary)">'+p.filename+' ('+p.size_mb+' MB)</span><span style="font-family:JetBrains Mono,monospace;font-size:12px;color:var(--green)">\u2713 uploaded</span></div><div class="progress-bar-outer"><div class="progress-bar-inner" style="width:100%;background:var(--green)"></div></div></div>')});
                if(d.gpg_key){pa.insertAdjacentHTML('beforeend','<div class="progress-item"><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-family:JetBrains Mono,monospace;font-size:13px;color:var(--text-secondary)">'+d.gpg_key.filename+'</span><span style="font-family:JetBrains Mono,monospace;font-size:12px;color:var(--green)">\u2713 uploaded</span></div><div class="progress-bar-outer"><div class="progress-bar-inner" style="width:100%;background:var(--green)"></div></div></div>')}
                if(d.policy){pa.insertAdjacentHTML('beforeend','<div class="progress-item"><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-family:JetBrains Mono,monospace;font-size:13px;color:var(--text-secondary)">'+d.policy.filename+'</span><span style="font-family:JetBrains Mono,monospace;font-size:12px;color:var(--green)">\u2713 uploaded</span></div><div class="progress-bar-outer"><div class="progress-bar-inner" style="width:100%;background:var(--green)"></div></div></div>')}
                var a=document.getElementById('upload-area');if(a){a.style.maxHeight='120px';a.style.padding='20px';var ic=a.querySelector('.upload-icon');if(ic)ic.style.display='none'}
                updateUploadSummary();
                applyUploadsModeDetection();
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

let uploadedFiles={packages:[],gpg_key:null,policy:null};
let uploadsInProgress=0;
let takDeploymentConfigCache=null;

function handleDragOver(e){e.preventDefault();document.getElementById('upload-area').classList.add('dragover')}
function handleDragLeave(e){document.getElementById('upload-area').classList.remove('dragover')}
function handleDrop(e){e.preventDefault();document.getElementById('upload-area').classList.remove('dragover');queueFiles(e.dataTransfer.files)}
function handleFileSelect(e){queueFiles(e.target.files);e.target.value=''}
function handleAddMore(e){queueFiles(e.target.files);e.target.value=''}

function formatSize(b){if(b<1024)return b+' B';if(b<1024*1024)return(b/1024).toFixed(1)+' KB';if(b<1024*1024*1024)return(b/(1024*1024)).toFixed(1)+' MB';return(b/(1024*1024*1024)).toFixed(2)+' GB'}

async function removeFile(fn,elId){
    try{await fetch('/api/upload/takserver/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:fn})})}catch(e){}
    var el=document.getElementById(elId);if(el)el.remove();
    if(uploadedFiles.packages)uploadedFiles.packages=uploadedFiles.packages.filter(function(p){return p.filename!==fn});
    if(uploadedFiles.gpg_key&&uploadedFiles.gpg_key.filename===fn)uploadedFiles.gpg_key=null;
    if(uploadedFiles.policy&&uploadedFiles.policy.filename===fn)uploadedFiles.policy=null;
    updateUploadSummary();
}

function queueFiles(fl){
    const a=document.getElementById('upload-area');if(a){a.style.maxHeight='120px';a.style.padding='20px';const ic=a.querySelector('.upload-icon');if(ic)ic.style.display='none'}
    for(const f of fl){
        var isDupe=false;
        if(uploadedFiles.packages&&uploadedFiles.packages.some(function(p){return p.filename===f.name}))isDupe=true;
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
        if(xhr.status===200){const d=JSON.parse(xhr.responseText);bar.style.background='var(--green)';pc.style.color='var(--green)';if(d.packages&&d.packages.length)d.packages.forEach(function(p){if(!uploadedFiles.packages.some(function(x){return x.filename===p.filename}))uploadedFiles.packages.push(p)});else if(d.package){var p=d.package;if(!uploadedFiles.packages.some(function(x){return x.filename===p.filename}))uploadedFiles.packages.push({filename:p.filename,filepath:p.filepath,size_mb:p.size_mb})}if(d.gpg_key)uploadedFiles.gpg_key=d.gpg_key;if(d.policy)uploadedFiles.policy=d.policy;var rBtn=document.createElement('span');rBtn.textContent=' \u2717';rBtn.style.cssText='color:var(--red);cursor:pointer;margin-left:8px';rBtn.title='Remove';rBtn.onclick=function(ev){ev.stopPropagation();removeFile(file.name,id)};pc.textContent='\u2713 ';pc.appendChild(rBtn);updateUploadSummary();applyUploadsModeDetection();}
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
    (uploadedFiles.packages||[]).forEach(function(p){h+='<div style="margin-bottom:8px">✓ <span style="color:var(--green)">'+p.filename+'</span> <span style="color:var(--text-dim)">('+p.size_mb+' MB)</span></div>'});
    if(uploadedFiles.gpg_key)h+='<div style="margin-bottom:8px">✓ <span style="color:var(--green)">'+uploadedFiles.gpg_key.filename+'</span> <span style="color:var(--text-dim)">(GPG key)</span></div>';
    if(uploadedFiles.policy)h+='<div style="margin-bottom:8px">✓ <span style="color:var(--green)">'+uploadedFiles.policy.filename+'</span> <span style="color:var(--text-dim)">(policy)</span></div>';
    if(uploadedFiles.gpg_key&&uploadedFiles.policy)h+='<div style="margin-top:12px;color:var(--green)">🔐 GPG verification enabled</div>';
    else if(!uploadedFiles.gpg_key&&!uploadedFiles.policy)h+='<div style="margin-top:12px;color:var(--text-dim)">\u2139 No GPG key/policy - verification will be skipped</div>';
    else h+='<div style="margin-top:12px;color:var(--yellow)">\u26a0 Need both GPG key + policy for verification</div>';
    fl.innerHTML=h;
    if(uploadedFiles.packages&&uploadedFiles.packages.length)document.getElementById('deploy-btn-area').style.display='block';
}

function showDeployConfig(){
    var validation=validateUploadsForMode();
    if(!validation.ok){alert(validation.message);return;}
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
      '<div class="form-field"><label>Country (2 letters)</label><input type="text" id="cert_country" placeholder="US" maxlength="2" style="text-transform:uppercase" pattern="[A-Za-z0-9 \'()+,\\-./:=?]*" title="No underscores, @, #, ! — only letters, numbers, spaces, and basic punctuation"></div>',
      '<div class="form-field"><label>State/Province</label><input type="text" id="cert_state" placeholder="CA" style="text-transform:uppercase" pattern="[A-Za-z0-9 \'()+,\\-./:=?]*" title="No underscores, @, #, ! — only letters, numbers, spaces, and basic punctuation"></div>',
      '<div class="form-field"><label>City</label><input type="text" id="cert_city" placeholder="SACRAMENTO" style="text-transform:uppercase" pattern="[A-Za-z0-9 \'()+,\\-./:=?]*" title="No underscores, @, #, ! — only letters, numbers, spaces, and basic punctuation"></div>',
      '<div class="form-field"><label>Organization</label><input type="text" id="cert_org" placeholder="MYAGENCY" style="text-transform:uppercase" pattern="[A-Za-z0-9 \'()+,\\-./:=?]*" title="No underscores, @, #, ! — only letters, numbers, spaces, and basic punctuation"></div>',
      '<div class="form-field"><label>Organizational Unit</label><input type="text" id="cert_ou" placeholder="IT" style="text-transform:uppercase" pattern="[A-Za-z0-9 \'()+,\\-./:=?]*" title="No underscores, @, #, ! — only letters, numbers, spaces, and basic punctuation"></div>',
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
      '<div id="cert-download-area" style="display:none;margin-top:20px"><div class="section-title">Download Certificates</div><div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:24px"><div class="cert-downloads"><a href="/api/download/admin-cert" class="cert-btn cert-btn-secondary">\u2B07 admin.p12</a><a href="/api/download/user-cert" class="cert-btn cert-btn-secondary">\u2B07 user.p12</a><a href="/api/download/truststore" class="cert-btn cert-btn-secondary">\u2B07 truststore.p12</a></div><div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;color:var(--text-dim);margin-top:12px">Certificate password: <span id="deploy-cert-password-inline" style="color:var(--cyan)">loading...</span></div></div></div>'
    ].join('');
    main.appendChild(cd);
    loadTakCertPassword();
    initTakDeployModeUI(cd);
    var modeChosenOnPage=getTakDeploymentMode();
    loadTakDeploymentConfig().then(function(){
      var single=document.getElementById('dep_mode_single');
      var split=document.getElementById('dep_mode_split');
      if(modeChosenOnPage==='two_server'&&split){split.checked=true;if(single)single.checked=false;}
      else if(single){single.checked=true;if(split)split.checked=false;}
      toggleTwoServerPanel();
      updateUploadHint();
      updateDeployModeFirstHint();
    });
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

function initTakDeployModeUI(rootEl){
    var card=rootEl&&rootEl.querySelector('div[style*="background:var(--bg-card)"]');
    if(!card)return;
    var html=[
      '<div id="two-server-config-panel" style="display:none;margin-bottom:20px;padding:16px;background:rgba(59,130,246,0.06);border:1px solid var(--border);border-radius:10px">',
      '<div style="font-family:\'JetBrains Mono\',monospace;font-size:13px;color:var(--text-dim);margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;font-weight:600">Split Server Wizard (Manual Naming)</div>',
      '<div style="font-size:12px;color:var(--text-dim);margin-bottom:10px">Server One = Database Server. Server Two = Core Server.</div>',
      '<label style="display:flex;align-items:center;gap:8px;color:var(--text-secondary);cursor:pointer;font-size:12px;margin-bottom:12px"><input type="checkbox" id="ts_server_two_local" checked onchange="toggleServerTwoLocal()" style="accent-color:var(--accent)"> Use this infra-TAK host as Server Two (Core Server)</label>',
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">',
      '<div style="background:var(--bg-surface);border:1px solid var(--border);border-radius:8px;padding:12px">',
      '<div style="font-size:12px;color:var(--cyan);font-weight:600;margin-bottom:8px">Server One: Database Server</div>',
      '<div class="form-field"><label>Host / IP</label><input type="text" id="ts_server_one_host" placeholder="10.0.0.21"></div>',
      '<div class="form-field"><label>SSH User</label><input type="text" id="ts_server_one_user" placeholder="root"></div>',
      '<div class="form-field"><label>SSH Port</label><input type="number" id="ts_server_one_port" value="22"></div>',
      '<div class="form-field"><label>Auth Method</label><select id="ts_server_one_auth" onchange="toggleTwoServerAuthInputs(\'one\')" style="width:100%;padding:10px 14px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;color:var(--text-primary);font-family:\'JetBrains Mono\',monospace;font-size:13px"><option value="ssh_key">SSH key</option><option value="password">User/password</option></select></div>',
      '<div class="form-field" id="ts_server_one_key_wrap"><label>SSH Key Path</label><input type="text" id="ts_server_one_key" placeholder="~/.ssh/id_rsa"></div>',
      '<div class="form-field" id="ts_server_one_pw_wrap" style="display:none"><label>SSH Password</label><input type="password" id="ts_server_one_pw" placeholder="Password"></div>',
      '</div>',
      '<div style="background:var(--bg-surface);border:1px solid var(--border);border-radius:8px;padding:12px">',
      '<div style="font-size:12px;color:var(--cyan);font-weight:600;margin-bottom:8px">Server Two: Core Server</div>',
      '<div class="form-field"><label>Host / IP</label><input type="text" id="ts_server_two_host" placeholder="10.0.0.22"></div>',
      '<div class="form-field"><label>SSH User</label><input type="text" id="ts_server_two_user" placeholder="root"></div>',
      '<div class="form-field"><label>SSH Port</label><input type="number" id="ts_server_two_port" value="22"></div>',
      '<div class="form-field"><label>Auth Method</label><select id="ts_server_two_auth" onchange="toggleTwoServerAuthInputs(\'two\')" style="width:100%;padding:10px 14px;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;color:var(--text-primary);font-family:\'JetBrains Mono\',monospace;font-size:13px"><option value="ssh_key">SSH key</option><option value="password">User/password</option></select></div>',
      '<div class="form-field" id="ts_server_two_key_wrap"><label>SSH Key Path</label><input type="text" id="ts_server_two_key" placeholder="~/.ssh/id_rsa"></div>',
      '<div class="form-field" id="ts_server_two_pw_wrap" style="display:none"><label>SSH Password</label><input type="password" id="ts_server_two_pw" placeholder="Password"></div>',
      '</div>',
      '</div>',
      '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:12px">',
      '<div class="form-field"><label>DB Port</label><input type="number" id="ts_db_port" value="5432"></div>',
      '<div class="form-field"><label>DB Name</label><input type="text" id="ts_db_name" value="cot"></div>',
      '<div class="form-field"><label>DB User</label><input type="text" id="ts_db_user" value="martiuser"></div>',
      '</div>',
      '<div id="ts_db_password_row" style="margin-top:10px"><div class="form-field"><label>DB password (from Server One)</label><input type="password" id="ts_db_password" placeholder="Filled automatically when you run step 4" autocomplete="off" style="width:100%;padding:8px 12px;background:#0a0e1a;border:1px solid var(--border);border-radius:6px;color:var(--text-primary);font-family:\'JetBrains Mono\',monospace;font-size:12px"></div>',
      '<div id="ts_db_password_hint" style="font-size:11px;color:var(--text-dim);margin-top:4px">Step 4 reads this from Server One over SSH when it deploys (same connection that installs the DB). You only need to paste here if step 4 failed to read it.</div></div>',
      '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px">',
      '<button type="button" onclick="saveTakDeploymentConfig()" style="padding:8px 14px;background:rgba(59,130,246,0.15);color:var(--accent);border:1px solid var(--border);border-radius:8px;font-size:12px;cursor:pointer">1. Save Config</button>',
      '<button type="button" onclick="ensureTakSshKey()" style="padding:8px 14px;background:rgba(139,92,246,0.15);color:var(--purple, #a78bfa);border:1px solid var(--border);border-radius:8px;font-size:12px;cursor:pointer">2. Setup SSH key</button>',
      '<button type="button" onclick="installTakSshKey()" style="padding:8px 14px;background:rgba(245,158,11,0.15);color:var(--amber, #f59e0b);border:1px solid var(--border);border-radius:8px;font-size:12px;cursor:pointer">3. Copy key to Server One</button>',
      '<button type="button" onclick="deployTakServerOne()" style="padding:8px 14px;background:rgba(99,102,241,0.2);color:var(--indigo,#6366f1);border:1px solid var(--border);border-radius:8px;font-size:12px;cursor:pointer">4. Deploy Server One (DB)</button>',
      '<button type="button" onclick="deployTakServerTwo()" style="padding:8px 14px;background:rgba(34,197,94,0.2);color:var(--green);border:1px solid var(--border);border-radius:8px;font-size:12px;cursor:pointer">5. Deploy Server Two (Core)</button>',
      '</div>',
      '<div id="two-server-msg" style="margin-top:10px;font-size:12px;color:var(--text-dim)"></div>',
      '<div id="two-server-preflight" style="display:none;margin-top:10px;background:#0c0f1a;border:1px solid var(--border);border-radius:8px;padding:12px;font-family:\'JetBrains Mono\',monospace;font-size:11px;white-space:pre-wrap"></div>',
      '<div id="two-server-runbook" style="display:none;margin-top:10px;background:#0c0f1a;border:1px solid var(--border);border-radius:8px;padding:12px;font-family:\'JetBrains Mono\',monospace;font-size:11px;white-space:pre-wrap"></div>',
      '</div>'
    ].join('');
    card.insertAdjacentHTML('afterbegin',html);
    var single=document.getElementById('dep_mode_single');
    var split=document.getElementById('dep_mode_split');
    if(single)single.addEventListener('change',toggleTwoServerPanel);
    if(split)split.addEventListener('change',toggleTwoServerPanel);
    toggleTwoServerPanel();
    toggleServerTwoLocal();
}

function getTakDeploymentMode(){
    var checked=document.querySelector('input[name="deployment_mode"]:checked');
    return checked?checked.value:'single_server';
}

function updateDeployModeFirstHint(){
    var el=document.getElementById('deploy-mode-first-hint');
    if(!el)return;
    var mode=getTakDeploymentMode();
    el.textContent=(mode==='two_server')
      ?'Split mode: upload both takserver-database and takserver-core packages (optional: .pol + .key).'
      :'One server: upload the single takserver package (optional: .pol + .key).';
}

function packageHasDatabase(fn){return fn&&String(fn).toLowerCase().indexOf('database')!==-1;}
function packageHasCore(fn){return fn&&String(fn).toLowerCase().indexOf('core')!==-1;}
function hasBothSplitPackages(){
  var pkg=uploadedFiles.packages||[];
  return pkg.some(function(p){return packageHasDatabase(p.filename);})&&pkg.some(function(p){return packageHasCore(p.filename);});
}
function hasOnlySplitPackages(){
  var pkg=uploadedFiles.packages||[];
  if(pkg.length===0)return false;
  return pkg.every(function(p){return packageHasDatabase(p.filename)||packageHasCore(p.filename);});
}
function applyUploadsModeDetection(){
  if(!hasBothSplitPackages())return;
  var split=document.getElementById('dep_mode_split');
  if(split&&!split.checked){split.checked=true;document.getElementById('dep_mode_single').checked=false;toggleTwoServerPanel();updateUploadHint();updateDeployModeFirstHint();}
}
function validateUploadsForMode(){
  var mode=getTakDeploymentMode();
  var pkg=uploadedFiles.packages||[];
  if(pkg.length===0)return{ok:true};
  if(mode==='two_server'){
    if(!hasBothSplitPackages())return{ok:false,message:'Split server requires both takserver-database and takserver-core packages. Upload both, or switch to One Server and upload the single takserver package.'};
    return{ok:true};
  }
  if(hasOnlySplitPackages()||pkg.some(function(p){return packageHasCore(p.filename)||packageHasDatabase(p.filename);})){
    return{ok:false,message:'You chose One Server but uploaded split packages (core and/or database). For One Server upload the single takserver .deb/.rpm. Or switch to Split Server and upload both database and core.'};
  }
  return{ok:true};
}

function updateUploadHint(){
    var el=document.getElementById('upload-requirements-hint');
    if(!el)return;
    var mode=getTakDeploymentMode();
    var osType=(document.getElementById('upload-area')||{}).getAttribute('data-os-type')||'';
    var ubuntu=osType.indexOf('ubuntu')!==-1;
    var rocky=osType.indexOf('rocky')!==-1||osType.indexOf('rhel')!==-1;
    var line2='<br><span style="color:var(--text-dim);font-size:11px">Select all at once or add files one at a time</span>';
    var html;
    if(mode==='two_server'){
      if(ubuntu)html='<strong style="color:var(--text-secondary)">Split server (Ubuntu) — from tak.gov:</strong><br>Required: <span style="color:var(--cyan)">takserver-database_X.X_all.deb</span> and <span style="color:var(--cyan)">takserver-core_X.X_all.deb</span><br>Optional: <span style="color:var(--text-secondary)">deb_policy.pol</span> + <span style="color:var(--text-secondary)">takserver-public-gpg.key</span>'+line2;
      else if(rocky)html='<strong style="color:var(--text-secondary)">Split server (Rocky/RHEL) — from tak.gov:</strong><br>Required: <span style="color:var(--cyan)">takserver-database</span> and <span style="color:var(--cyan)">takserver-core</span> .rpm<br>Optional: <span style="color:var(--text-secondary)">takserver-public-gpg.key</span>'+line2;
      else html='<strong style="color:var(--text-secondary)">Split server:</strong><br>Required: <span style="color:var(--cyan)">takserver-database</span> and <span style="color:var(--cyan)">takserver-core</span> .deb or .rpm<br>Optional: .pol + .key'+line2;
    }else{
      if(ubuntu)html='<strong style="color:var(--text-secondary)">One server (Ubuntu) — from tak.gov:</strong><br>Required: <span style="color:var(--cyan)">takserver_X.X_all.deb</span><br>Optional: <span style="color:var(--text-secondary)">deb_policy.pol</span> + <span style="color:var(--text-secondary)">takserver-public-gpg.key</span>'+line2;
      else if(rocky)html='<strong style="color:var(--text-secondary)">One server (Rocky/RHEL) — from tak.gov:</strong><br>Required: <span style="color:var(--cyan)">takserver-X.X.noarch.rpm</span><br>Optional: <span style="color:var(--text-secondary)">takserver-public-gpg.key</span>'+line2;
      else html='<strong style="color:var(--text-secondary)">One server:</strong><br>Required: <span style="color:var(--cyan)">.deb</span> or <span style="color:var(--cyan)">.rpm</span> package<br>Optional: .pol + .key'+line2;
    }
    el.innerHTML=html;
}

function toggleTwoServerPanel(){
    var mode=getTakDeploymentMode();
    var panel=document.getElementById('two-server-config-panel');
    var hint=document.getElementById('dep_mode_hint');
    if(panel)panel.style.display=(mode==='two_server'?'block':'none');
    if(hint){
      hint.textContent=(mode==='two_server')
        ?'Split mode selected. Save config, run preflight, then apply Server One and Server Two steps in order.'
        :'One server selected. This path is recommended up to ~500 concurrent users.';
    }
    updateUploadHint();
}

function toggleServerTwoLocal(){
    var useLocal=!!(document.getElementById('ts_server_two_local')||{}).checked;
    var ids=['ts_server_two_host','ts_server_two_user','ts_server_two_port','ts_server_two_auth','ts_server_two_key','ts_server_two_pw'];
    ids.forEach(function(id){
      var el=document.getElementById(id);
      if(el)el.disabled=useLocal;
    });
    if(useLocal){
      var host=document.getElementById('ts_server_two_host');if(host)host.value='127.0.0.1';
      var user=document.getElementById('ts_server_two_user');if(user)user.value='root';
      var port=document.getElementById('ts_server_two_port');if(port)port.value='22';
      var auth=document.getElementById('ts_server_two_auth');if(auth)auth.value='ssh_key';
      var key=document.getElementById('ts_server_two_key');if(key)key.value='';
      var pw=document.getElementById('ts_server_two_pw');if(pw)pw.value='';
    }
    toggleTwoServerAuthInputs('two');
}

function toggleTwoServerAuthInputs(which){
    var auth=document.getElementById('ts_server_'+which+'_auth');
    var keyWrap=document.getElementById('ts_server_'+which+'_key_wrap');
    var pwWrap=document.getElementById('ts_server_'+which+'_pw_wrap');
    var usePw=auth&&auth.value==='password';
    if(keyWrap)keyWrap.style.display=usePw?'none':'block';
    if(pwWrap)pwWrap.style.display=usePw?'block':'none';
}

function collectTakDeploymentConfigFromForm(){
    return {
      mode:getTakDeploymentMode(),
      server_one:{
        host:(document.getElementById('ts_server_one_host')||{}).value||'',
        ssh_user:(document.getElementById('ts_server_one_user')||{}).value||'root',
        ssh_port:parseInt((document.getElementById('ts_server_one_port')||{}).value||'22',10),
        auth_method:(document.getElementById('ts_server_one_auth')||{}).value||'ssh_key',
        ssh_key_path:(document.getElementById('ts_server_one_key')||{}).value||'',
        ssh_password:(document.getElementById('ts_server_one_pw')||{}).value||''
      },
      server_two:{
        host:(document.getElementById('ts_server_two_host')||{}).value||'',
        ssh_user:(document.getElementById('ts_server_two_user')||{}).value||'root',
        ssh_port:parseInt((document.getElementById('ts_server_two_port')||{}).value||'22',10),
        use_localhost:!!(document.getElementById('ts_server_two_local')||{}).checked,
        auth_method:(document.getElementById('ts_server_two_auth')||{}).value||'ssh_key',
        ssh_key_path:(document.getElementById('ts_server_two_key')||{}).value||'',
        ssh_password:(document.getElementById('ts_server_two_pw')||{}).value||''
      },
      database:{
        port:parseInt((document.getElementById('ts_db_port')||{}).value||'5432',10),
        name:(document.getElementById('ts_db_name')||{}).value||'cot',
        user:(document.getElementById('ts_db_user')||{}).value||'martiuser',
        password:(document.getElementById('ts_db_password')||{}).value||''
      }
    };
}

function populateTakDeploymentConfigForm(cfg){
    if(!cfg)return;
    takDeploymentConfigCache=cfg;
    if(cfg.mode==='two_server'){
      var split=document.getElementById('dep_mode_split');if(split)split.checked=true;
    }else{
      var single=document.getElementById('dep_mode_single');if(single)single.checked=true;
    }
    toggleTwoServerPanel();
    function set(id,val){var el=document.getElementById(id);if(el&&typeof val!=='undefined'&&val!==null)el.value=String(val);}
    set('ts_server_one_host',cfg.server_one&&cfg.server_one.host);
    set('ts_server_one_user',cfg.server_one&&cfg.server_one.ssh_user);
    set('ts_server_one_port',cfg.server_one&&cfg.server_one.ssh_port);
    set('ts_server_one_auth',cfg.server_one&&cfg.server_one.auth_method);
    set('ts_server_one_key',cfg.server_one&&cfg.server_one.ssh_key_path);
    set('ts_server_one_pw',cfg.server_one&&cfg.server_one.ssh_password);
    set('ts_server_two_host',cfg.server_two&&cfg.server_two.host);
    set('ts_server_two_user',cfg.server_two&&cfg.server_two.ssh_user);
    set('ts_server_two_port',cfg.server_two&&cfg.server_two.ssh_port);
    var s2Local=document.getElementById('ts_server_two_local');
    if(s2Local)s2Local.checked=!!(cfg.server_two&&cfg.server_two.use_localhost);
    set('ts_server_two_auth',cfg.server_two&&cfg.server_two.auth_method);
    set('ts_server_two_key',cfg.server_two&&cfg.server_two.ssh_key_path);
    set('ts_server_two_pw',cfg.server_two&&cfg.server_two.ssh_password);
    set('ts_db_port',cfg.database&&cfg.database.port);
    set('ts_db_name',cfg.database&&cfg.database.name);
    set('ts_db_user',cfg.database&&cfg.database.user);
    set('ts_db_password',cfg.database&&cfg.database.password);
    var pwHint=document.getElementById('ts_db_password_hint');
    if(pwHint){pwHint.textContent=(cfg.database&&cfg.database.password)?'✓ DB password saved (from step 4). Step 5 and Deploy TAK Server will use it.':'Step 4 reads this from Server One over SSH when it deploys. Paste here only if step 4 could not read it.';}
    toggleTwoServerAuthInputs('one');
    toggleTwoServerAuthInputs('two');
    toggleServerTwoLocal();
    updateUploadHint();
    updateDeployModeFirstHint();
}

async function loadTakDeploymentConfig(){
    try{
      var r=await fetch('/api/takserver/deployment-config');
      var d=await r.json();
      if(d&&d.config)populateTakDeploymentConfigForm(d.config);
    }catch(e){}
}

async function saveTakDeploymentConfig(silent){
    var msg=document.getElementById('two-server-msg');
    try{
      var cfg=collectTakDeploymentConfigFromForm();
      var r=await fetch('/api/takserver/deployment-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({config:cfg})});
      var d=await r.json();
      if(!d.success)throw new Error(d.error||'Save failed');
      takDeploymentConfigCache=d.config;
      if(msg&&!silent){msg.textContent='✓ Split config saved';msg.style.color='var(--green)';}
      return d.config;
    }catch(e){
      if(msg&&!silent){msg.textContent='✗ '+e.message;msg.style.color='var(--red)';}
      throw e;
    }
}

async function openTakDbFirewall(){
    var msg=document.getElementById('two-server-msg');
    if(msg){msg.textContent='Preparing Server One (installing DB if needed, configuring PG + firewall…)';msg.style.color='var(--cyan)';}
    try{
      var cfg=collectTakDeploymentConfigFromForm();
      var r=await fetch('/api/takserver/two-server/open-db-firewall',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({config:cfg})});
      var d=await r.json();
      if(!d.success)throw new Error(d.error||'Failed');
      if(msg){msg.textContent='✓ '+(d.message||'Server One ready');msg.style.color='var(--green)';}
      return d;
    }catch(e){
      if(msg){msg.textContent='✗ '+e.message;msg.style.color='var(--red)';}
      throw e;
    }
}

async function runTakTwoServerPreflight(silent){
    var msg=document.getElementById('two-server-msg');
    var out=document.getElementById('two-server-preflight');
    try{
      var cfg=await saveTakDeploymentConfig(true);
      if(out){out.style.display='block';out.textContent='Running preflight...';}
      var r=await fetch('/api/takserver/two-server/preflight',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({config:cfg})});
      var d=await r.json();
      var lines=['Two-Server Preflight'];
      (d.checks||[]).forEach(function(c){lines.push((c.ok?'[OK] ':'[FAIL] ')+c.name+(c.details?(' - '+c.details):''));});
      if(out)out.textContent=lines.join('\n');
      if(msg&&!silent){msg.textContent=d.success?'✓ Preflight passed':'⚠ Preflight has failures';msg.style.color=d.success?'var(--green)':'var(--yellow)';}
      return d;
    }catch(e){
      if(out){out.style.display='block';out.textContent='Preflight error: '+e.message;}
      if(msg&&!silent){msg.textContent='✗ '+e.message;msg.style.color='var(--red)';}
      return {success:false,error:e.message};
    }
}

async function ensureTakSshKey(){
    var msg=document.getElementById('two-server-msg');
    try{
      var cfg=collectTakDeploymentConfigFromForm();
      var r=await fetch('/api/takserver/two-server/ensure-ssh-key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({config:cfg})});
      var d=await r.json();
      if(!d.success)throw new Error(d.error||'Setup failed');
      if(msg){msg.textContent='✓ '+(d.message||'Key ready')+(d.fingerprint?' — '+d.fingerprint:'');msg.style.color='var(--green)';}
      return d;
    }catch(e){
      if(msg){msg.textContent='✗ '+e.message;msg.style.color='var(--red)';}
      throw e;
    }
}

async function installTakSshKey(){
    var msg=document.getElementById('two-server-msg');
    var password=prompt('Server One SSH password (one-time; not stored):');
    if(password==null)return;
    if(!password.trim()){if(msg){msg.textContent='No password entered.';msg.style.color='var(--yellow)';}return;}
    try{
      var cfg=collectTakDeploymentConfigFromForm();
      var r=await fetch('/api/takserver/two-server/install-ssh-key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({config:cfg,password:password})});
      var d=await r.json();
      if(!d.success)throw new Error(d.error||'Install failed');
      if(msg){msg.textContent='✓ '+(d.message||'Key installed on Server One');msg.style.color='var(--green)';}
      return d;
    }catch(e){
      if(msg){msg.textContent='✗ '+e.message;msg.style.color='var(--red)';}
      throw e;
    }
}

async function deployTakServerOne(){
    var msg=document.getElementById('two-server-msg');
    if(msg){msg.textContent='Deploying to Server One (copying package, installing… may take a few minutes)';msg.style.color='var(--cyan)';}
    try{
      var cfg=collectTakDeploymentConfigFromForm();
      var r=await fetch('/api/takserver/two-server/deploy-server-one',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({config:cfg})});
      var d=await r.json();
      if(!d.success)throw new Error(d.error||'Deploy failed');
      if(d.db_password_captured){
        if(msg){msg.textContent='✓ Server One ready. DB password captured automatically. Move to step 5 (Deploy Server Two).';msg.style.color='var(--green)';}
        loadTakDeploymentConfig();
      }else{
        if(msg){msg.textContent='✓ Server One ready. DB password was not captured — step 5 needs it. Paste the password from Server One in the field above and Save Config, then move to step 5.';msg.style.color='var(--yellow)';}
      }
      return d;
    }catch(e){
      if(msg){msg.textContent='✗ '+e.message;msg.style.color='var(--red)';}
      console.error('deployTakServerOne error:', e);
    }
}

async function deployTakServerTwo(){
    var msg=document.getElementById('two-server-msg');
    if(msg){msg.textContent='Deploying to Server Two (this host)…';msg.style.color='var(--cyan)';}
    try{
      var cfg=collectTakDeploymentConfigFromForm();
      var r=await fetch('/api/takserver/two-server/deploy-server-two',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({config:cfg})});
      var d=await r.json();
      if(!d.success)throw new Error(d.error||'Deploy failed');
      if(msg){msg.textContent='✓ '+(d.message||'Server Two deploy complete');msg.style.color='var(--green)';}
      loadTakDeploymentConfig();
      return d;
    }catch(e){
      if(msg){msg.textContent='✗ '+e.message;msg.style.color='var(--red)';}
      console.error('deployTakServerTwo error:', e);
    }
}

async function loadTakTwoServerRunbook(){
    var msg=document.getElementById('two-server-msg');
    var out=document.getElementById('two-server-runbook');
    try{
      await saveTakDeploymentConfig(true);
      var r=await fetch('/api/takserver/two-server/runbook');
      var d=await r.json();
      if(!d.success)throw new Error(d.error||'Runbook failed');
      var lines=['Two-Server Runbook (Manual Naming)','','Server One: Database Server'];
      (d.server_one_steps||[]).forEach(function(s){lines.push(s);});
      lines.push('','Server Two: Core Server');
      (d.server_two_steps||[]).forEach(function(s){lines.push(s);});
      if(d.notes&&d.notes.length){lines.push('','Notes:');d.notes.forEach(function(n){lines.push('- '+n);});}
      if(out){out.style.display='block';out.textContent=lines.join('\n');}
      if(msg){msg.textContent='✓ Runbook generated';msg.style.color='var(--green)';}
      return d;
    }catch(e){
      if(out){out.style.display='block';out.textContent='Runbook error: '+e.message;}
      if(msg){msg.textContent='✗ '+e.message;msg.style.color='var(--red)';}
      return {success:false,error:e.message};
    }
}

async function startDeploy(){
    var deploymentMode=getTakDeploymentMode();
    if(deploymentMode==='two_server'){
      if(!confirm('Two-server mode: This will generate certificates, configure auth, and finish the TAK Server setup on this host (Server Two). Make sure steps 1-6 are complete. Continue?'))return;
    }
    const rf=[{id:'cert_country',l:'Country'},{id:'cert_state',l:'State'},{id:'cert_city',l:'City'},{id:'cert_org',l:'Organization'},{id:'cert_ou',l:'Org Unit'},{id:'root_ca_name',l:'Root CA'},{id:'intermediate_ca_name',l:'Intermediate CA'}];
    const empty=rf.filter(f=>!document.getElementById(f.id).value.trim());
    if(empty.length>0){alert('Please fill in: '+empty.map(f=>f.l).join(', '));empty.forEach(f=>{const el=document.getElementById(f.id);el.style.borderColor='var(--red)';el.addEventListener('input',()=>el.style.borderColor='',{once:true})});return}
    const asn1ok=/^[A-Za-z0-9 '()+,\-./:=?]*$/;const certFields=[{id:'cert_country',l:'Country'},{id:'cert_state',l:'State'},{id:'cert_city',l:'City'},{id:'cert_org',l:'Organization'},{id:'cert_ou',l:'Org Unit'}];
    const badFields=certFields.filter(f=>{const v=document.getElementById(f.id).value.trim();return v&&!asn1ok.test(v)});
    if(badFields.length>0){alert('Invalid characters in: '+badFields.map(f=>f.l).join(', ')+'\n\nCertificate fields only allow: A-Z, 0-9, spaces, and \' ( ) + , - . / : = ?\n\nNo underscores, @, #, ! or special characters.');badFields.forEach(f=>{const el=document.getElementById(f.id);el.style.borderColor='var(--red)';el.addEventListener('input',()=>el.style.borderColor='',{once:true})});return}
    const aui=document.getElementById('enable_admin_ui').checked;
    if(aui){const p=document.getElementById('webadmin_password').value;const pc=document.getElementById('webadmin_password_confirm').value;if(!p){alert('Please set a webadmin password.');return}if(p!==pc){alert('Passwords do not match.');return}if(!validatePassword()){alert('Password does not meet requirements.');return}}
    const btn=document.getElementById('deploy-btn');btn.disabled=true;btn.textContent='Deploying...';btn.style.opacity='0.6';btn.style.cursor='not-allowed';
    document.querySelectorAll('.form-field input,input[type="checkbox"]').forEach(el=>el.disabled=true);
    const cfg={cert_country:document.getElementById('cert_country').value.toUpperCase(),cert_state:document.getElementById('cert_state').value.toUpperCase(),cert_city:document.getElementById('cert_city').value.toUpperCase(),cert_org:document.getElementById('cert_org').value.toUpperCase(),cert_ou:document.getElementById('cert_ou').value.toUpperCase(),root_ca_name:document.getElementById('root_ca_name').value.toUpperCase(),intermediate_ca_name:document.getElementById('intermediate_ca_name').value.toUpperCase(),enable_admin_ui:document.getElementById('enable_admin_ui').checked,enable_webtak:document.getElementById('enable_webtak').checked,enable_nonadmin_ui:document.getElementById('enable_nonadmin_ui').checked,webadmin_password:aui?document.getElementById('webadmin_password').value:'',deployment_mode:deploymentMode};
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
var upgradeXhr=null,upgradeFileReady=false;
function cancelUpgradeUpload(){
  if(upgradeXhr){upgradeXhr.abort();upgradeXhr=null;}
  upgradeFileReady=false;
  var pa=document.getElementById('upgrade-progress-area');if(pa)pa.innerHTML='';
  var ua=document.getElementById('upgrade-upload-area');if(ua){ua.style.maxHeight='';ua.style.padding='';}
}
function uploadUpgradeDeb(file){
  if(!file||!file.name.toLowerCase().endsWith('.deb')){var m=document.getElementById('tak-update-msg');if(m){m.textContent='Select a .deb file.';m.style.color='var(--red)';}return;}
  var pa=document.getElementById('upgrade-progress-area');
  pa.innerHTML='';
  var fnEl=document.getElementById('upgrade-filename');if(fnEl){fnEl.style.display='none';}
  var ua=document.getElementById('upgrade-upload-area');if(ua){ua.style.maxHeight='80px';ua.style.padding='16px';}
  var row=document.createElement('div');row.className='progress-item';
  var top=document.createElement('div');top.style.cssText='display:flex;justify-content:space-between;align-items:center';
  var lbl=document.createElement('span');lbl.style.cssText='font-family:JetBrains Mono,monospace;font-size:13px;color:var(--text-secondary)';lbl.textContent=file.name+' ('+formatSize(file.size)+')';
  var right=document.createElement('span');right.style.cssText='display:flex;align-items:center;gap:8px';
  var pct=document.createElement('span');pct.style.cssText='font-family:JetBrains Mono,monospace;font-size:12px;color:var(--cyan)';pct.textContent='0%';
  var cancelBtn=document.createElement('span');cancelBtn.textContent='\u2717';cancelBtn.style.cssText='color:var(--red);cursor:pointer;font-size:14px';cancelBtn.title='Cancel upload';
  cancelBtn.onclick=function(){cancelUpgradeUpload();};
  right.appendChild(pct);right.appendChild(cancelBtn);top.appendChild(lbl);top.appendChild(right);
  var barOuter=document.createElement('div');barOuter.className='progress-bar-outer';
  var barInner=document.createElement('div');barInner.className='progress-bar-inner';barInner.style.width='0%';
  barOuter.appendChild(barInner);row.appendChild(top);row.appendChild(barOuter);pa.appendChild(row);
  var fd=new FormData();fd.append('files',file);
  var xhr=new XMLHttpRequest();
  upgradeXhr=xhr;
  xhr.upload.onprogress=function(e){if(e.lengthComputable){var p=Math.round((e.loaded/e.total)*100);barInner.style.width=p+'%';pct.textContent=p+'%';}};
  xhr.onload=function(){
    upgradeXhr=null;barInner.style.width='100%';cancelBtn.remove();
    if(xhr.status===200){var d=JSON.parse(xhr.responseText);if(d.error){barInner.style.background='var(--red)';pct.textContent=d.error;pct.style.color='var(--red)';return;}
      barInner.style.background='var(--green)';pct.style.color='var(--green)';pct.textContent='\u2713 ';
      var rBtn=document.createElement('span');rBtn.textContent='\u2717';rBtn.style.cssText='color:var(--red);cursor:pointer;margin-left:8px;font-size:14px';rBtn.title='Remove';rBtn.onclick=function(){cancelUpgradeUpload();};pct.appendChild(rBtn);
      upgradeFileReady=true;if(fnEl){fnEl.textContent=file.name;fnEl.style.display='block';}var m=document.getElementById('tak-update-msg');if(m)m.textContent='';}
    else{barInner.style.background='var(--red)';pct.textContent='\u2717';pct.style.color='var(--red)';}
  };
  xhr.onerror=function(){upgradeXhr=null;barInner.style.background='var(--red)';pct.textContent='\u2717 Failed';pct.style.color='var(--red)';};
  xhr.onabort=function(){upgradeXhr=null;};
  xhr.timeout=1800000;
  xhr.ontimeout=function(){upgradeXhr=null;barInner.style.background='var(--red)';pct.textContent='Timeout';pct.style.color='var(--red)';};
  xhr.open('POST','/api/upload/takserver');xhr.send(fd);
}
function handleUpgradeFile(ev){
  var files=ev.target.files;
  for(var i=0;i<files.length;i++){uploadUpgradeDeb(files[i]);}
}
function handleUpgradeDrop(ev){
  ev.preventDefault();ev.stopPropagation();
  document.getElementById('upgrade-upload-area').classList.remove('dragover');
  var files=ev.dataTransfer.files;
  for(var i=0;i<files.length;i++){uploadUpgradeDeb(files[i]);}
}
function takToggleUpdate(){takToggleSection('tak-update');}
function takToggleSection(id){var body=document.getElementById(id+'-body');var icon=document.getElementById(id+'-toggle-icon');if(!body)return;var show=body.style.display==='none';body.style.display=show?'block':'none';if(icon)icon.style.transform=show?'rotate(180deg)':'';}
async function startTakUpdate(){
  var btn=document.getElementById('tak-update-btn');var msg=document.getElementById('tak-update-msg');
  if(!upgradeFileReady){if(msg){msg.textContent='Upload a .deb package first.';msg.style.color='var(--red)';}return;}
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
      if(!d.running){var btn=document.getElementById('tak-update-btn');if(btn)btn.disabled=false;if(d.complete){if(btn)btn.textContent='Update complete';var m=document.getElementById('tak-update-msg');if(m)m.textContent='Done. Refreshing...';setTimeout(function(){location.reload();},2000);}else if(d.error){var m=document.getElementById('tak-update-msg');if(m){m.textContent='Update failed';m.style.color='var(--red)';}}}else{setTimeout(poll,800);}
    });
  }
  poll();
}
if(document.body.getAttribute('data-tak-deploying')==='true' && document.getElementById('deploy-log')){ pollDeployLog(); }
if(document.body.getAttribute('data-tak-upgrading')==='true' && document.getElementById('upgrade-log')){ upgradeLogIndex=0; pollUpgradeLog(); }
