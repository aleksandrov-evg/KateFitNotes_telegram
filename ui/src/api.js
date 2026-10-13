export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}
export class Api {
  constructor({fetcher = globalThis.fetch.bind(globalThis), storage = globalThis.sessionStorage, onUnauthorized = () => {}} = {}) {
    this.fetcher = fetcher; this.storage = storage; this.onUnauthorized = onUnauthorized;
    this.token = storage.getItem('katefit-token') || '';
  }
  setToken(token) { this.token = token; token ? this.storage.setItem('katefit-token',token) : this.storage.removeItem('katefit-token'); }
  async request(path, {method = 'GET', body, signal} = {}) {
    let response;
    try {
      response = await this.fetcher(`/api/v1${path}`, {
        method, signal: signal ?? AbortSignal.timeout(20000), cache:'no-store',
        headers:{...(body ? {'Content-Type':'application/json'} : {}), ...(this.token ? {Authorization:`Bearer ${this.token}`} : {})},
        ...(body ? {body:JSON.stringify(body)} : {}),
      });
    } catch (error) {
      if (error.name === 'AbortError') throw error;
      throw new ApiError(method === 'GET' ? 'Не удалось связаться с сервером. Проверьте соединение и повторите загрузку.' : 'Ответ сервера не получен. Перед повторной отправкой обновите данные и проверьте, сохранилась ли операция.',0);
    }
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      if (response.status === 401 && path !== '/auth/login') { this.setToken(''); this.onUnauthorized(); }
      let message = typeof data?.detail === 'string' ? data.detail : 'Не удалось выполнить запрос. Попробуйте позже.';
      if (response.status === 422 && Array.isArray(data?.detail)) message = 'Проверьте заполнение полей: сервер отклонил данные.';
      if (response.status >= 500) message = 'Сервер временно недоступен. Повторите попытку позже.';
      throw new ApiError(message,response.status);
    }
    return data;
  }
  async all(path, params = {}) {
    const items = [];
    for (let offset = 0; ; ) {
      const query = new URLSearchParams({...params,limit:100,offset});
      const page = await this.request(`${path}?${query}`);
      items.push(...page.items);
      offset += page.items.length;
      if (offset >= page.total) return items;
      if (!page.items.length) throw new ApiError('Список изменился во время загрузки. Обновите данные.',0);
    }
  }
}
