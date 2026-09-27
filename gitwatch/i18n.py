"""Translate server-generated dashboard errors without changing stored/user content."""

ENGLISH = {
    'Укажи ссылку вида https://github.com/owner/repository.': 'Enter a URL like https://github.com/owner/repository.',
    'Нужна ссылка на сам репозиторий: https://github.com/owner/repository.': 'Enter the repository URL: https://github.com/owner/repository.',
    'Поддерживаются ссылки на репозитории github.com без дополнительных параметров.': 'Use a github.com repository URL without extra parameters.',
    'Интервал должен быть целым числом от 1 до 1440 минут.': 'The interval must be a whole number from 1 to 1440 minutes.',
    'Выбери все ветки, основную или указанную ветку.': 'Choose all branches, the default branch or a specific branch.',
    'Укажи имя ветки.': 'Enter a branch name.',
    'Укажи корректное имя ветки, например main или feature/example.': 'Enter a valid branch name, such as main or feature/example.',
    'GitHub ограничил частоту запросов. Проверки продолжатся автоматически.': 'GitHub rate limit reached. Checks will resume automatically.',
    'Нет соединения с GitHub. Повторим проверку автоматически.': 'Could not connect to GitHub. Checks will retry automatically.',
    'GitHub не принял токен. Обнови его в настройках.': 'GitHub rejected the token. Update it in settings.',
    'Репозиторий или ветка не найдены. Для приватного репозитория проверь доступ токена.': 'Repository or branch not found. For a private repository, check token access.',
    'GitHub ограничил запросы или доступ. Проверь разрешения токена; опрос возобновится автоматически.': 'GitHub limited requests or access. Check token permissions; polling will resume automatically.',
    'GitHub временно не вернул данные. Повторим проверку.': 'GitHub did not return data. The check will retry.',
    'GitHub вернул некорректный ответ. Повторим проверку.': 'GitHub returned an invalid response. The check will retry.',
    'GitHub вернул некорректный список веток.': 'GitHub returned an invalid branch list.',
    'GitHub вернул некорректный список веток. Обнови список.': 'GitHub returned an invalid branch list. Refresh the list.',
    'Слишком много веток. Выбери одну ветку для этого репозитория.': 'Too many branches. Choose one branch for this repository.',
    'Нет ответа от Telegram. Повторим автоматически.': 'Telegram did not respond. The request will retry automatically.',
    'Telegram не принял токен бота.': 'Telegram rejected the bot token.',
    'Бот заблокирован. Открой чат и нажми «Запустить».': 'The bot is blocked. Open its chat and select Start.',
    'Токен бота уже используется другим приложением. Создай отдельного бота.': 'Another application is using this bot token. Create a dedicated bot.',
    'Telegram ограничил частоту сообщений. Отправка продолжится автоматически.': 'Telegram rate limit reached. Delivery will resume automatically.',
    'Telegram не смог выполнить запрос. Проверь подключение.': 'Telegram could not complete the request. Check the connection.',
    'Этот репозиторий уже добавлен. Измени его настройки в списке.': 'This repository is already added. Edit its settings in the list.',
    'Этот репозиторий уже добавлен.': 'This repository is already added.',
    'Можно отслеживать до 100 репозиториев.': 'You can monitor up to 100 repositories.',
    'Репозиторий уже удалён.': 'This repository has already been removed.',
    'Репозиторий удалён.': 'Repository removed.',
    'Настройки уже изменились. Обнови страницу и повтори.': 'Settings have changed. Refresh the page and try again.',
    'Некорректное состояние мониторинга.': 'Invalid monitoring state.',
    'GitHub вернул некорректные данные веток. Повторим проверку.': 'GitHub returned invalid branch data. The check will retry.',
    'Ветка пока не существует. Продолжаем наблюдение.': 'The branch does not exist yet. Monitoring will continue.',
    'Не удалось обработать ответ GitHub. Повторим проверку автоматически.': 'Could not process the GitHub response. Checks will retry automatically.',
    'Укажи @ник своего личного Telegram-аккаунта.': 'Enter the @username of your personal Telegram account.',
    'Подключения уже изменились. Открой настройки заново.': 'Connection settings have changed. Reopen settings.',
    'Укажи токен бота, полученный у @BotFather.': 'Enter the bot token you received from @BotFather.',
    'У этого бота включён webhook другого приложения. Создай отдельного бота в @BotFather.': 'This bot has a webhook for another application. Create a dedicated bot with @BotFather.',
    'Telegram не подтвердил бота.': 'Telegram could not verify the bot.',
    'Получатель Telegram изменён.': 'The Telegram recipient has changed.',
    'Telegram отключён.': 'Telegram disconnected.',
    'Некорректный GitHub-токен.': 'Invalid GitHub token.',
    'Сначала отправь боту /start со своего аккаунта.': 'First send /start to the bot from your account.',
    'Временная ошибка. Повторяем автоматически.': 'Temporary error. Retrying automatically.',
    'Запрос отклонён. Открой сайт напрямую и повтори.': 'Request rejected. Open the dashboard directly and try again.',
    'Запрос с другого сайта отклонён.': 'A request from another site was rejected.',
    'Ожидается JSON-запрос.': 'A JSON request is required.',
    'Запрос не выполнен. Проверь адрес и данные.': 'Request failed. Check the URL and request data.',
    'Не удалось выполнить запрос. Обнови страницу и повтори.': 'The request failed. Refresh the page and try again.',
    'Некорректный формат запроса. Обнови страницу.': 'Invalid request format. Refresh the page.',
}


def translate(message, language='ru'):
    return ENGLISH.get(message, message) if language == 'en' else message


def translate_snapshot(snapshot, language):
    # The snapshot is a fresh response object; stored errors are left unchanged.
    for repo in snapshot['repos']:
        repo['last_error'] = translate(repo['last_error'], language)
    for event in snapshot['events']:
        event['error'] = translate(event['error'], language)
    telegram = snapshot['settings']['telegram']
    telegram['error'] = translate(telegram['error'], language)
    return snapshot
