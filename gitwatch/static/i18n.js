'use strict';

// Each message keeps its English and Russian versions together.
const GitWatchI18n = (() => {
  const messages = {
    title: ['Git Watch · Repositories', 'Git Watch · Репозитории'],
    description: ['Monitor GitHub repositories and get Telegram notifications about new changes.', 'Мониторинг GitHub-репозиториев и уведомления о новых изменениях в Telegram.'],
    language: ['Interface language', 'Язык интерфейса'],
    brandTag: ['PERSONAL MONITOR', 'ЛИЧНЫЙ МОНИТОР'],
    settings: ['Settings', 'Настройки'],
    heading: ['Your repositories, on watch', 'Репозитории под наблюдением'],
    subtitle: ['New commits and branch changes — right after each check.', 'Новые коммиты и изменения веток — сразу после проверки.'],
    connecting: ['Connecting…', 'Подключение…'],
    summary: ['Monitoring summary', 'Сводка мониторинга'],
    watching: ['Watching', 'Отслеживаются'],
    changes24h: ['Changes in 24 hours', 'Изменения за 24 часа'],
    pending: ['Pending delivery', 'Ожидают отправки'],
    repositories: ['My repositories', 'Мои репозитории'],
    checkAll: ['↻ Check now', '↻ Проверить'],
    add: ['+ Add', '+ Добавить'],
    addRepository: ['+ Add repository', '+ Добавить репозиторий'],
    emptyReposTitle: ['Add your first repository', 'Добавь первый репозиторий'],
    emptyReposBody: ['Paste a GitHub URL and choose how often to check for changes.', 'Вставь ссылку с GitHub и выбери, как часто проверять изменения.'],
    baselineShort: ['The first check establishes a baseline. Notifications start with new changes.', 'Первый опрос запомнит текущее состояние. Уведомления придут только о новых изменениях.'],
    telegramPitch: ['A push on GitHub. A message for you.', 'Пуш в GitHub. Сообщение тебе.'],
    telegramIntro: ['Connect a bot and enter your @username to receive updates in a private chat.', 'Подключи бота и укажи свой @ник, чтобы получать уведомления в личном чате.'],
    connectTelegram: ['Connect Telegram', 'Подключить Telegram'],
    botSettings: ['Bot settings', 'Настройки бота'],
    openBot: ['Open bot →', 'Открыть бота →'],
    sendTest: ['Send a test', 'Отправить тест'],
    howItWorks: ['HOW IT WORKS', 'КАК ЭТО РАБОТАЕТ'],
    stepRepo: ['Add a repository URL', 'Добавь ссылку на репозиторий'],
    stepRepoHelp: ['Public, or private with a GitHub token.', 'Публичный или приватный с GitHub-токеном.'],
    stepInterval: ['Choose a check interval', 'Настрой частоту проверок'],
    stepIntervalHelp: ['Set branches and frequency for each repository.', 'Свой интервал и ветки для каждого репозитория.'],
    stepNotify: ['Get notified about a push', 'Получи сообщение о пуше'],
    stepNotifyHelp: ['The branch, commits and a link to the changes.', 'Ветка, коммиты и ссылка на изменения.'],
    recentChanges: ['Recent changes', 'Последние изменения'],
    historyLocal: ['History is stored on your device', 'История сохраняется на устройстве'],
    historyLimit: ['Latest 60 events · kept for 90 days', 'Последние 60 событий · хранение 90 дней'],
    emptyEventsTitle: ['New changes will appear here', 'Здесь появятся новые изменения'],
    emptyEventsBody: ['Git Watch starts checking automatically after you add a repository.', 'После добавления репозитория Git Watch начнёт проверки автоматически.'],
    waiting: ['Waiting for data…', 'Ожидание данных…'],
    monitoring: ['MONITORING', 'МОНИТОРИНГ'],
    repoAdd: ['Add repository', 'Добавить репозиторий'],
    repoEdit: ['Repository settings', 'Настройки репозитория'],
    close: ['Close', 'Закрыть'],
    githubUrl: ['GitHub URL', 'Ссылка на GitHub'],
    privateRepoHelp: ['For a private repository, add a GitHub token in settings first.', 'Для приватного репозитория сначала добавь GitHub-токен в настройках.'],
    whichBranches: ['Branches to watch', 'Какие ветки проверять'],
    allBranches: ['All branches', 'Все ветки'],
    defaultBranch: ['Default branch', 'Основная ветка'],
    defaultBranchOption: ['Default branch', 'Основную ветку'],
    chooseBranch: ['Choose a branch', 'Выбрать ветку'],
    interval: ['Interval, minutes', 'Интервал, минут'],
    branch: ['Branch', 'Ветка'],
    enterRepoFirst: ['Enter a repository URL first', 'Сначала укажи ссылку на репозиторий'],
    branchesAuto: ['Branches load automatically from GitHub.', 'Список загрузится с GitHub автоматически.'],
    refreshBranches: ['↻ Refresh list', '↻ Обновить список'],
    baseline: ['The first check establishes a baseline. Previous commits will not be sent to Telegram.', 'Первый опрос создаёт точку отсчёта. Старые коммиты не будут отправлены в Telegram.'],
    cancel: ['Cancel', 'Отмена'],
    save: ['Save', 'Сохранить'],
    connections: ['CONNECTIONS', 'ПОДКЛЮЧЕНИЯ'],
    telegramBot: ['Telegram bot', 'Telegram-бот'],
    botHelp: ['Create a dedicated bot with <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">@BotFather</a>. Use its token only with this service.', 'Создай отдельного бота через <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">@BotFather</a>. Один токен должен использоваться только этим сервисом.'],
    botToken: ['Bot token', 'Токен бота'],
    tokenServer: ['The token is stored only on the server.', 'Токен хранится только на сервере.'],
    telegramUsername: ['Your Telegram username', 'Твой ник в Telegram'],
    bindHelp: ['After saving, send <code>/start</code> to the bot from your account. Other users and group chats are ignored.', 'После сохранения отправь боту <code>/start</code> со своего аккаунта. Другие пользователи и групповые чаты игнорируются.'],
    disconnect: ['Disconnect', 'Отключить'],
    saveTelegram: ['Save Telegram', 'Сохранить Telegram'],
    githubAccess: ['GitHub access', 'Доступ к GitHub'],
    githubHelp: ['A token enables private repositories and more frequent checks. For selected repositories, <code>Contents: Read-only</code> is enough.', 'Токен нужен для приватных репозиториев и более частых проверок. Для выбранных репозиториев достаточно разрешения <code>Contents: Read-only</code>.'],
    githubPublic: ['Public repositories are available without a token.', 'Публичные репозитории доступны без токена.'],
    removeToken: ['Remove token', 'Удалить токен'],
    saveGithub: ['Save GitHub', 'Сохранить GitHub'],
    confirmRemove: ['Remove repository?', 'Удалить репозиторий?'],
    remove: ['Remove', 'Удалить'],
    confirmRemoveBody: ['Monitoring of {name} will stop. Its change history will remain on the dashboard.', 'Наблюдение за {name} прекратится. История изменений останется на сайте.'],
    never: ['Not yet', 'Ещё не было'],
    minutes: ['{count} min', '{count} мин'],
    hours: ['{count} h', '{count} ч'],
    every: ['Every {interval}', 'Каждые {interval}'],
    push: ['New push', 'Новый пуш'],
    rewrite: ['Branch history changed', 'История ветки изменена'],
    branchCreated: ['New branch', 'Новая ветка'],
    branchDeleted: ['Branch deleted', 'Ветка удалена'],
    changes: ['Changes', 'Изменения'],
    queued: ['Queued', 'В очереди'],
    sent: ['Sent to Telegram', 'В Telegram'],
    telegramDisabled: ['Telegram not configured', 'Telegram не настроен'],
    skipped: ['Not sent', 'Без отправки'],
    paused: ['Paused', 'На паузе'],
    checkingGithub: ['Checking GitHub…', 'Проверяем GitHub…'],
    checkQueued: ['Check queued', 'Проверка в очереди'],
    inSeconds: ['In {count} sec', 'Через {count} сек'],
    inMinutes: ['In {count} min', 'Через {count} мин'],
    running: ['Monitoring is running', 'Мониторинг работает'],
    stopped: ['Monitoring is stopped', 'Мониторинг не запущен'],
    checking: ['Checking', 'Проверяем'],
    needsAttention: ['Needs attention', 'Нужна проверка'],
    watchingBadge: ['Watching', 'Наблюдение'],
    firstCheck: ['First check', 'Первый опрос'],
    checkNow: ['Check now', 'Проверить сейчас'],
    checkRepo: ['Check {name}', 'Проверить {name}'],
    pause: ['Pause', 'Приостановить'],
    resume: ['Resume', 'Возобновить'],
    pauseRepo: ['Pause {name}', 'Приостановить {name}'],
    resumeRepo: ['Resume {name}', 'Возобновить {name}'],
    repoSettings: ['Settings for {name}', 'Настройки {name}'],
    removeRepo: ['Remove {name}', 'Удалить {name}'],
    lastChecked: ['Last checked: {time}', 'Последняя проверка: {time}'],
    connectionError: ['Connection error', 'Ошибка связи'],
    connected: ['Connected', 'Подключён'],
    waitingStart: ['Waiting for /start', 'Ждём /start'],
    notConfigured: ['Not configured', 'Не настроен'],
    botConnected: ['Your bot sends changes to your private chat and responds to commands.', 'Бот присылает изменения в твой личный чат и отвечает на команды.'],
    botWaiting: ['Open the bot and send <code>/start</code> from your account to link the chat.', 'Открой бота и отправь <code>/start</code> со своего аккаунта для привязки чата.'],
    viaProxy: ['Via proxy', 'Через прокси'],
    commits: ['Commits: {count}', 'Коммитов: {count}'],
    updated: ['Updated {time} · every 5 sec', 'Обновлено {time} · каждые 5 сек'],
    rate: ['GitHub: {remaining} of {limit} requests left. Limit resets {time}.', 'GitHub: осталось {remaining} из {limit} запросов. Лимит обновится {time}.'],
    ratePause: ['GitHub rate limit reached. Checks resume automatically after {time}.', 'Пауза по лимиту GitHub до {time}. Проверки возобновятся автоматически.'],
    refreshError: ['Could not refresh data. {message}', 'Не удалось обновить данные. {message}'],
    offline: ['Device is offline', 'Нет связи с устройством'],
    networkError: ['Could not connect. Check your connection and try again.', 'Не удалось подключиться. Проверь соединение и повтори.'],
    incompleteResponse: ['The server returned an incomplete response. Try again.', 'Сервер вернул неполный ответ. Повтори запрос.'],
    requestError: ['The request failed. Try again.', 'Не удалось выполнить запрос.'],
    branchesLoading: ['Loading branches…', 'Загрузка веток…'],
    branchLoadError: ['Could not load branches.', 'Не удалось загрузить ветки.'],
    branchesEmpty: ['This repository has no branches yet', 'В репозитории пока нет веток'],
    branchDefaultSuffix: [' — default', ' — основная'],
    branchMissingSuffix: [' — saved, currently missing', ' — сохранённая, сейчас не найдена'],
    branchesFetching: ['Loading branches from GitHub…', 'Загружаем ветки с GitHub…'],
    branchMissing: ['The saved branch is currently missing on GitHub. Keep watching it or choose another branch.', 'Сохранённая ветка сейчас отсутствует на GitHub. Можно оставить наблюдение за ней или выбрать другую.'],
    branchesFound: ['Branches found: {count}.', 'Найдено веток: {count}.'],
    defaultBranchName: [' Default: {name}.', ' Основная: {name}.'],
    branchesEmptyHelp: ['This repository has no branches yet. You can choose “All branches”.', 'В репозитории пока нет веток. Можно выбрать «Все ветки».'],
    branchesPaste: ['Paste a repository URL to load its branches automatically.', 'Вставь ссылку на репозиторий — список загрузится автоматически.'],
    branchReadError: ['Could not read the branch list. Refresh the list.', 'Не удалось прочитать список веток. Обнови список.'],
    waitConnection: ['Wait for the device to connect.', 'Дождись соединения с устройством.'],
    tokenSaved: ['Token saved. Leave this field empty to keep it.', 'Токен сохранён. Оставь поле пустым, чтобы его не менять.'],
    githubTokenSavedNote: ['GitHub token saved. Enter a new token to replace it.', 'GitHub-токен сохранён. Введи новый для замены.'],
    githubWithoutToken: ['Without a token: public repositories only, up to 60 requests per hour per IP.', 'Без токена доступны только публичные репозитории: до 60 запросов в час с одного IP.'],
    checkRequested: ['Check requested. Results will appear here.', 'Проверка запрошена. Результат появится здесь.'],
    monitoringPaused: ['Monitoring paused.', 'Мониторинг приостановлен.'],
    monitoringResumed: ['Monitoring resumed.', 'Мониторинг возобновлён.'],
    testSent: ['Test message sent.', 'Тестовое сообщение отправлено.'],
    telegramDisconnected: ['Telegram disconnected.', 'Telegram отключён.'],
    githubTokenRemoved: ['GitHub token removed.', 'GitHub-токен удалён.'],
    waitBranches: ['Wait for branches to load and choose one from the list.', 'Дождись загрузки веток и выбери ветку из списка.'],
    settingsSaved: ['Settings saved.', 'Настройки сохранены.'],
    repoAdded: ['Repository added. Monitoring is starting.', 'Репозиторий добавлен. Начинаем наблюдение.'],
    telegramSaved: ['Telegram saved. Send /start to your bot to link your account.', 'Telegram сохранён. Отправь боту /start для привязки.'],
    enterGithubToken: ['Enter a GitHub token. Use the separate button to remove it.', 'Введи GitHub-токен. Для удаления используй отдельную кнопку.'],
    githubTokenSaved: ['GitHub token saved.', 'GitHub-токен сохранён.'],
    repoRemoved: ['Repository removed.', 'Репозиторий удалён.'],
    required: ['Fill in this field.', 'Заполни это поле.'],
    invalidInterval: ['Enter a whole number from 1 to 1440 minutes.', 'Укажи целое число от 1 до 1440 минут.'],
  };
  const storageKey = 'gitwatch.language';
  const supported = value => value === 'en' || value === 'ru';

  function detectLanguage(saved, languages = []) {
    if (supported(saved)) return saved;
    for (const value of languages) {
      const candidate = String(value).toLowerCase().split('-')[0];
      if (supported(candidate)) return candidate;
    }
    return 'en';
  }

  function create({storage, languages = []} = {}) {
    let saved;
    try { saved = storage?.getItem(storageKey); } catch { /* Storage can be disabled. */ }
    let language = detectLanguage(saved, languages);
    const t = (key, values = {}) => {
      const text = messages[key]?.[language === 'ru' ? 1 : 0] ?? key;
      return text.replace(/\{(\w+)\}/g, (match, name) => Object.hasOwn(values, name) ? String(values[name]) : match);
    };
    const setLanguage = value => {
      if (!supported(value)) return false;
      language = value;
      try { storage?.setItem(storageKey, value); } catch { /* Keep the choice for this session. */ }
      return true;
    };
    const apply = root => {
      for (const node of root.querySelectorAll('[data-i18n]')) node.textContent = t(node.dataset.i18n);
      // Only trusted static catalog entries use HTML. User and repository data never enter this path.
      for (const node of root.querySelectorAll('[data-i18n-html]')) node.innerHTML = t(node.dataset.i18nHtml);
      for (const attr of ['aria-label', 'title', 'placeholder', 'content']) {
        for (const node of root.querySelectorAll(`[data-i18n-${attr}]`)) node.setAttribute(attr, t(node.getAttribute(`data-i18n-${attr}`)));
      }
    };
    return {t, setLanguage, apply, get language() { return language; }, get locale() { return language === 'ru' ? 'ru-RU' : 'en-US'; }};
  }
  return {create, detectLanguage, messages, storageKey};
})();

if (typeof module !== 'undefined' && module.exports) module.exports = GitWatchI18n;
