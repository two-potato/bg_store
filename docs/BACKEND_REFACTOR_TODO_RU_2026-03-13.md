# Backend Refactor TODO

Цель: привести `backend` к понятной структуре, где:

- web/html/views код лежит в папках `views/`
- DRF/API код лежит в папках `api/`
- старые flat-модули остаются только как compatibility shim там, где это нужно для мягкого перехода

## План

~~- [ ] Перенести shopfront view-модули в `backend/shopfront/views/`~~
~~- [ ] Перенести users html view-модули в `backend/users/views/`~~
~~- [ ] Вынести catalog API в `backend/catalog/api/`~~
~~- [ ] Вынести orders API в `backend/orders/api/`~~
~~- [ ] Вынести commerce API в `backend/commerce/api/`~~
~~- [ ] Вынести users API в `backend/users/api/`~~
~~- [ ] Перенести core view-модуль в `backend/core/views/`~~
~~- [ ] Обновить `urls.py` и прямые импорты на новую canonical-структуру~~
~~- [ ] Оставить compatibility shims для старых import paths~~
~~- [ ] Прогнать compile/check тестового среза~~

## Статус

- Завершено
