// Minimal HTMX CSRF support for Django (no frameworks)
(function(){
  function getCookie(name){
    const v = document.cookie.split('; ').find(row => row.startsWith(name + '='));
    return v ? decodeURIComponent(v.split('=')[1]) : null;
  }
  document.addEventListener('htmx:configRequest', function(e){
    const token = getCookie('csrftoken') || document.querySelector('meta[name="csrf-token"]')?.content;
    if(token){ e.detail.headers['X-CSRFToken'] = token; }
  });
})();

