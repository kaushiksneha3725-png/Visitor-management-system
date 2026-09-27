(function(){
  const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
  document.addEventListener('submit', function(e){
    const form = e.target;
    if(form.matches('[data-confirm]') && !window.confirm(form.getAttribute('data-confirm'))) e.preventDefault();
  });
  const toggle = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  if(toggle && sidebar){ toggle.addEventListener('click', ()=>sidebar.classList.toggle('open')); }
  window.refreshNotifications = async function(){
    try{
      const r = await fetch('/notifications/api', {headers:{'Accept':'application/json'}});
      if(!r.ok) return;
      const data = await r.json();
      const nav = document.getElementById('navUnread'); const top=document.getElementById('topUnread');
      if(nav) nav.textContent=data.unread; if(top){top.textContent=data.unread; top.classList.toggle('d-none', data.unread===0);}
    }catch(e){}
  };
  window.initLiveVisitors = function(){
    const body=document.getElementById('liveBody'); if(!body) return;
    const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
    async function load(){
      try{
        const r=await fetch('/api/live-visitors',{headers:{'Accept':'application/json'}}); if(!r.ok) return; const rows=await r.json();
        body.innerHTML=rows.length?rows.map(v=>`<tr><td class="font-monospace">${esc(v.visitor_id)}</td><td class="fw-semibold">${esc(v.name)}</td><td>${esc(v.host)}</td><td>${esc(v.purpose)}</td><td>${esc(v.check_in_time)}</td><td>${esc(v.duration)}</td><td><span class="status-badge status-checked-in">Checked In</span></td><td class="text-end"><a class="btn btn-sm btn-light border" href="${esc(v.details_url)}">View</a></td></tr>`).join(''):`<tr><td colspan="8" class="text-center py-5 text-secondary">No visitors are currently inside.</td></tr>`;
      }catch(e){}
    }
    load(); setInterval(load,12000);
  };
  setInterval(window.refreshNotifications,15000);
  window.addEventListener('load', ()=>window.refreshNotifications());
})();
