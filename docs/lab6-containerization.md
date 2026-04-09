# Лабораторная работа №6. Контейнеризация и автоматизация развертывания

## 1. Архитектура контейнеризации

### 1.1. Сервисы приложения

- `web`: Nginx reverse proxy + статическая раздача React SPA.
- `api`: FastAPI backend.
- `db`: PostgreSQL 16.
- `object_storage`: отдельный контейнер не нужен; для MVP используется постоянный volume, примонтированный в `api`.
- `CI/CD`: GitHub Actions как вспомогательный сервис автоматизации сборки и развертывания.

### 1.2. Сетевая схема

- Внешний трафик приходит на `web` по HTTP.
- `web` проксирует `/api/*`, `/robots.txt`, `/sitemap.xml` в `api`.
- `api` ходит в `db` по внутренней сети `backend`.
- `db` не имеет опубликованных портов наружу.
- Данные PostgreSQL и файлового хранилища сохраняются в named volumes.

## 2. Контейнеризация компонентов

- Frontend развертывается через Nginx и multi-stage `Dockerfile.web`.
- Backend упакован в отдельный `server/Dockerfile`.
- Добавлены root `.dockerignore` и `server/.dockerignore`.
- Для backend реализован entrypoint с ожиданием готовности БД.

## 3. Оркестрация через Docker Compose

- Один `docker compose up --build` поднимает `web`, `api`, `db`.
- Настроены volumes: `postgres_data`, `object_storage`.
- Настроены сети: `edge`, `backend`.
- Для `db`, `api`, `web` добавлены healthcheck.
- Использован `depends_on.condition: service_healthy` для порядка запуска по готовности зависимостей.

## 4. Безопасная и управляемая конфигурация

- Все runtime-параметры вынесены в `.env`.
- В репозиторий добавлены только шаблоны `.env.example`, `.env.deploy.example`, `.env.ci.example`.
- `.gitignore` исключает реальные `.env.*` и артефакты тестов.
- Nginx добавляет базовые security headers.
- Backend работает не под root-пользователем в контейнере.

## 5. CI/CD

- GitHub Actions запускает:
  - `npm run lint`
  - `pytest`
  - `npm test`
  - `npm run test:e2e`
- После успешных проверок workflow собирает и публикует образы в GHCR.
- Для `master/main` выполняется автодеплой по SSH на сервер.

## 6. Устойчивость и наблюдаемость

- Падение сервиса: `restart: unless-stopped`.
- Недоступность БД на старте: backend entrypoint повторяет попытки подключения.
- Ошибки внешнего API: приложение уже возвращает контролируемые `502`, контейнеризация это не ломает.
- Health endpoint backend теперь показывает статус БД.
- Неуспешная инициализация схемы приводит к падению контейнера и повторному запуску после восстановления зависимости.
