(function(){
  function setAddrField(form, name, value) {
    var el = form.querySelector('[name="' + name + '"]');
    if (el && value) el.value = value;
  }

  function parseGmapsComponents(components) {
    var get = function(type){
      var found = components.find(function(c){ return c.types && c.types.includes(type); }) || {};
      return found.long_name || '';
    };
    var route = get('route');
    var streetNum = get('street_number');
    var locality = get('locality') || get('administrative_area_level_2') || get('administrative_area_level_1');
    return {
      country: get('country'),
      city: locality,
      street: [route, streetNum].filter(Boolean).join(', '),
      postcode: get('postal_code')
    };
  }

  function resolveAddress(form, lat, lon) {
    if (window.google && google.maps && google.maps.Geocoder) {
      var geocoder = new google.maps.Geocoder();
      geocoder.geocode({ location: { lat: lat, lng: lon } }, function(results, status){
        if (status === 'OK' && results && results[0]) {
          var addr = parseGmapsComponents(results[0].address_components);
          setAddrField(form, 'country', addr.country);
          setAddrField(form, 'city', addr.city);
          setAddrField(form, 'street', addr.street);
          setAddrField(form, 'postcode', addr.postcode);
        } else {
          window.ShopToast?.show({ message: 'Адрес не найден, заполните поля вручную', variant: 'danger' });
        }
      });
      return;
    }

    fetch('/api/commerce/lookup/revgeo/?lat=' + encodeURIComponent(lat) + '&lon=' + encodeURIComponent(lon))
      .then(function(resp){ if (!resp.ok) throw new Error('bad response'); return resp.json(); })
      .then(function(data){
        if (data && (data.city || data.street)) {
          setAddrField(form, 'country', data.country || '');
          setAddrField(form, 'city', data.city || '');
          setAddrField(form, 'street', data.street || '');
          setAddrField(form, 'postcode', data.postcode || '');
          return;
        }
        throw new Error('empty address');
      })
      .catch(function(){
        window.ShopToast?.show({ message: 'Адрес не найден, заполните поля вручную', variant: 'danger' });
      });
  }

  function geolocate(btn) {
    var form = btn.closest('form');
    if (!form) return;
    if (!navigator.geolocation) {
      window.ShopToast?.show({ message: 'Геолокация не поддерживается', variant: 'danger' });
      return;
    }

    btn.disabled = true;
    navigator.geolocation.getCurrentPosition(function(pos){
      resolveAddress(form, pos.coords.latitude, pos.coords.longitude);
      btn.disabled = false;
    }, function(err){
      window.ShopToast?.show({ message: 'Не удалось получить геопозицию: ' + err.message, variant: 'danger' });
      btn.disabled = false;
    }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
  }

  document.body.addEventListener('click', function(e){
    var btn = e.target.closest('[data-geolocate-btn]');
    if (!btn) return;
    e.preventDefault();
    geolocate(btn);
  });
})();
