/* FoodBridge main.js */

// ===== MOBILE NAV MENU =====
(function(){
  function closeNav(){
    var links=document.getElementById('navLinks');
    var btn=document.getElementById('navToggle');
    var overlay=document.getElementById('navOverlay');
    if(links) links.classList.remove('open');
    if(btn){ btn.classList.remove('active'); btn.setAttribute('aria-expanded','false'); }
    if(overlay) overlay.classList.remove('open');
  }
  function openNav(){
    var links=document.getElementById('navLinks');
    var btn=document.getElementById('navToggle');
    var overlay=document.getElementById('navOverlay');
    if(links) links.classList.add('open');
    if(btn){ btn.classList.add('active'); btn.setAttribute('aria-expanded','true'); }
    if(overlay) overlay.classList.add('open');
  }
  document.addEventListener('DOMContentLoaded', function(){
    var btn=document.getElementById('navToggle');
    var links=document.getElementById('navLinks');
    var overlay=document.getElementById('navOverlay');
    if(!btn || !links) return;
    btn.addEventListener('click', function(){
      if(links.classList.contains('open')) closeNav(); else openNav();
    });
    if(overlay) overlay.addEventListener('click', closeNav);
    // Close menu after tapping a link inside it
    links.querySelectorAll('a').forEach(function(a){ a.addEventListener('click', closeNav); });
    // Reset state when resizing back to desktop
    window.addEventListener('resize', function(){
      if(window.innerWidth > 860) closeNav();
    });
  });
})();

// ===== CHATBOT =====
function playBotSound(){
  var s=document.getElementById('botClickSound');
  if(s){ try{ s.currentTime=0; s.play().catch(function(){}); }catch(e){} }
}
function toggleBot(){
  var p=document.getElementById('botPanel');
  p.classList.toggle('open');
  playBotSound();
  if(p.classList.contains('open')){ var i=document.getElementById('botInput'); if(i) setTimeout(function(){i.focus();},200); }
}
function appendBotMsg(text,cls){
  var b=document.getElementById('botMessages');
  var d=document.createElement('div');
  d.className='msg '+cls;
  d.textContent=text;
  b.appendChild(d);
  b.scrollTop=b.scrollHeight;
  return d; // return the exact element so replies never overwrite the wrong bubble
}
var _botBusy=false;
async function askBot(){
  if(_botBusy) return; // prevents the assistant from answering twice on a fast double-send
  var inp=document.getElementById('botInput');
  var sendBtn=document.querySelector('.bot-send');
  var t=inp.value.trim();
  if(!t) return;
  _botBusy=true;
  if(sendBtn) sendBtn.disabled=true;
  inp.disabled=true;
  appendBotMsg(t,'user');
  inp.value='';
  var placeholder=appendBotMsg('Thinking…','bot typing');
  try{
    var r=await fetch('/bot/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:t})});
    var d=await r.json();
    placeholder.textContent=d.reply;
    placeholder.className='msg bot';
  }catch(e){
    placeholder.textContent='Error. Please try again.';
    placeholder.className='msg bot';
  }finally{
    _botBusy=false;
    if(sendBtn) sendBtn.disabled=false;
    inp.disabled=false;
    inp.focus();
  }
}
document.addEventListener('DOMContentLoaded',()=>{
  var i=document.getElementById('botInput');
  if(i)i.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();askBot();}});
  var sendBtn=document.querySelector('.bot-send');
  if(sendBtn) sendBtn.addEventListener('click', playBotSound);
});

// ===== GLOBAL initMap — used by all dashboards ===========================
// CRITICAL: elem must be in DOM and visible. We use setTimeout+invalidateSize.
window.initMap = function(id, lat, lng, label){
  var el = document.getElementById(id);
  if(!el || el._fb_map) return;
  el._fb_map = true;
  setTimeout(function(){
    var m = L.map(id, {zoomControl:false, scrollWheelZoom:false, attributionControl:false}).setView([lat,lng],15);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(m);
    var icon = L.divIcon({html:'<div style="font-size:28px;filter:drop-shadow(0 2px 6px rgba(0,0,0,.4))">🏪</div>',className:'',iconSize:[36,36],iconAnchor:[18,36]});
    L.marker([lat,lng],{icon}).addTo(m).bindPopup(label||'Location').openPopup();
    setTimeout(()=>m.invalidateSize(), 350);
  }, 100);
};

// ===== GPS SHARE (runner) =====
var _gpsWatchId = null;
function shareLocation(btn){
  if(!navigator.geolocation){alert('GPS not supported on this device');return;}
  if(_gpsWatchId){
    navigator.geolocation.clearWatch(_gpsWatchId); _gpsWatchId=null;
    if(btn){btn.textContent='📡 Share Live GPS';btn.classList.remove('gps-active');}
    return;
  }
  if(btn){btn.textContent='⏳ Starting GPS…';}
  _gpsWatchId = navigator.geolocation.watchPosition(async function(pos){
    if(btn){btn.textContent='📡 GPS Active ✅';btn.classList.add('gps-active');}
    try{await fetch('/gps/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({latitude:pos.coords.latitude,longitude:pos.coords.longitude})});}catch(e){}
  }, function(err){
    if(btn){btn.textContent='📡 Share Live GPS';}
    alert('GPS error: '+err.message);
  }, {enableHighAccuracy:true, timeout:15000});
}

// ===== REVERSE GEOCODE via Nominatim =====
async function reverseGeocode(lat, lng){
  try{
    var r=await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&addressdetails=1`,{headers:{'Accept-Language':'en'}});
    return await r.json();
  }catch(e){return null;}
}

// ===== REGISTRATION GPS =====
var _regMap=null,_regMarker=null;
async function captureRegistrationLocation(){
  if(!navigator.geolocation){alert('GPS not supported');return;}
  var status=document.getElementById('gpsStatus'),spinner=document.getElementById('gpsSpinner');
  if(status){status.style.display='block';status.textContent='📡 Getting location…';status.style.background='#fef3c7';status.style.color='#92400e';}
  if(spinner)spinner.style.display='inline';
  navigator.geolocation.getCurrentPosition(async function(pos){
    var lat=pos.coords.latitude,lng=pos.coords.longitude;
    var latEl=document.getElementById('gps_latitude'),lngEl=document.getElementById('gps_longitude');
    if(latEl)latEl.value=lat; if(lngEl)lngEl.value=lng;
    if(spinner)spinner.style.display='none';
    if(status)status.textContent='🔍 Fetching full address…';
    var geo=await reverseGeocode(lat,lng);
    if(geo&&geo.address){
      var a=geo.address;
      var street=([a.road,a.pedestrian].filter(Boolean).join(', '))||'';
      var area=a.suburb||a.neighbourhood||a.quarter||a.village||'';
      var city=a.city||a.town||a.county||'';
      var state=a.state||''; var pin=a.postcode||'';
      var short=[area,city,state,pin].filter(Boolean).join(', ');
      var locEl=document.getElementById('live_location_name');
      if(locEl)locEl.value=short||geo.display_name;
      var fEl=document.getElementById('full_address_display');if(fEl)fEl.value=geo.display_name;
      // Fill form fields
      var sEl=document.querySelector('input[name="street"]');if(sEl&&street)sEl.value=street;
      var aEl=document.querySelector('input[name="area"]');if(aEl&&area)aEl.value=area;
      var cEl=document.querySelector('input[name="city"]');if(cEl&&city)cEl.value=city;
      var stEl=document.querySelector('input[name="state"]');if(stEl&&state)stEl.value=state;
      var pEl=document.querySelector('input[name="pincode"]');if(pEl&&pin)pEl.value=pin;
      if(status){status.textContent='✅ '+short;status.style.background='#dcfce7';status.style.color='#166534';}
    } else {
      var locEl=document.getElementById('live_location_name');
      if(locEl)locEl.value='GPS: '+lat.toFixed(5)+', '+lng.toFixed(5);
      if(status){status.textContent='✅ GPS coordinates captured';status.style.background='#dcfce7';status.style.color='#166534';}
    }
    // Show map
    var mapDiv=document.getElementById('registerMap');
    if(mapDiv){
      mapDiv.style.display='block';
      setTimeout(function(){
        if(!_regMap){
          _regMap=L.map('registerMap',{zoomControl:true,scrollWheelZoom:false,attributionControl:false}).setView([lat,lng],16);
          L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(_regMap);
          _regMarker=L.marker([lat,lng]).addTo(_regMap).bindPopup('Your location').openPopup();
        } else { _regMarker.setLatLng([lat,lng]);_regMap.setView([lat,lng],16); }
        setTimeout(()=>_regMap.invalidateSize(),250);
      },80);
    }
  }, function(err){
    if(spinner)spinner.style.display='none';
    if(status){status.textContent='❌ GPS error: '+err.message;status.style.background='#fee2e2';status.style.color='#dc2626';}
  },{enableHighAccuracy:true,timeout:12000});
}

// ===== DONATION GPS =====
var _donMap=null,_donMarker=null;
async function captureDonationLocation(){
  if(!navigator.geolocation){alert('GPS not supported');return;}
  var status=document.getElementById('donationGpsStatus'),spinner=document.getElementById('donGpsSpinner');
  if(status){status.style.display='block';status.textContent='📡 Getting location…';status.style.background='#fef3c7';status.style.color='#92400e';}
  if(spinner)spinner.style.display='inline';
  navigator.geolocation.getCurrentPosition(async function(pos){
    var lat=pos.coords.latitude,lng=pos.coords.longitude;
    var latEl=document.getElementById('donation_latitude'),lngEl=document.getElementById('donation_longitude');
    if(latEl)latEl.value=lat; if(lngEl)lngEl.value=lng;
    if(spinner)spinner.style.display='none';
    if(status)status.textContent='🔍 Fetching address…';
    var geo=await reverseGeocode(lat,lng);
    var locEl=document.getElementById('donation_location');
    if(geo&&geo.address){
      var a=geo.address;
      var area=a.suburb||a.neighbourhood||a.quarter||a.village||'';
      var city=a.city||a.town||a.county||'';
      var state=a.state||'';var pin=a.postcode||'';
      var short=[area,city,state,pin].filter(Boolean).join(', ');
      if(locEl&&!locEl.value)locEl.value=short||geo.display_name;
      if(status){status.textContent='✅ '+short;status.style.background='#dcfce7';status.style.color='#166534';}
    } else {
      if(locEl&&!locEl.value)locEl.value='GPS: '+lat.toFixed(5)+', '+lng.toFixed(5);
      if(status){status.textContent='✅ GPS captured';status.style.background='#dcfce7';status.style.color='#166534';}
    }
    var mapDiv=document.getElementById('donationMap');
    if(mapDiv){
      mapDiv.style.display='block';
      setTimeout(function(){
        if(!_donMap){
          _donMap=L.map('donationMap',{zoomControl:true,scrollWheelZoom:false,attributionControl:false}).setView([lat,lng],16);
          L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(_donMap);
          _donMarker=L.marker([lat,lng]).addTo(_donMap).bindPopup('Pickup location').openPopup();
        } else { _donMarker.setLatLng([lat,lng]);_donMap.setView([lat,lng],16); }
        setTimeout(()=>_donMap.invalidateSize(),250);
      },80);
    }
  }, function(err){
    if(spinner)spinner.style.display='none';
    if(status){status.textContent='❌ GPS error: '+err.message;status.style.background='#fee2e2';status.style.color='#dc2626';}
  },{enableHighAccuracy:true,timeout:12000});
}

// ===== FORM VALIDATION =====
function validateRegisterForm(){
  var p=document.getElementById('password'),c=document.getElementById('confirm_password');
  if(p&&c&&p.value!==c.value){alert('Passwords do not match!');c.focus();return false;}
  if(p&&p.value.length<6){alert('Password must be at least 6 characters');p.focus();return false;}
  return true;
}
function togglePw(id,btn){
  var inp=document.getElementById(id);
  if(inp.type==='password'){inp.type='text';btn.textContent='🙈';}
  else{inp.type='password';btn.textContent='👁';}
}

// ===== TAB HELPER =====
function showTab(id,btn){
  document.querySelectorAll('.tab-panel').forEach(p=>p.style.display='none');
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById(id).style.display='block'; btn.classList.add('active');
}
