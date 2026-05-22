document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.hasAttribute("data-async-form")) {
    return;
  }

  event.preventDefault();
  const targetSelector = form.dataset.target;
  const submitLabel = form.dataset.submitLabel || "Получить ответ";
  const loadingLabel = form.dataset.loadingLabel || "Ищу ответ...";
  const loadingMessage = form.dataset.loadingMessage || "Ищу релевантные фрагменты и готовлю ответ...";
  const successMessage = form.dataset.successMessage || "Готово.";
  const reloadOnSuccess = form.dataset.reloadOnSuccess === "true";
  const target = targetSelector ? document.querySelector(targetSelector) : null;
  const button = form.querySelector("button[type='submit']");
  const errorMessage = form.dataset.errorMessage || "Запрос не прошел. Проверь сервер и API key.";
  const errorTitle = form.dataset.errorTitle || "Не удалось получить ответ.";
  if (button) {
    button.disabled = true;
    button.textContent = loadingLabel;
    button.setAttribute("aria-busy", "true");
  }
  if (target) {
    target.innerHTML = `<div class="status-box">${escapeHtml(loadingMessage)}</div>`;
  }

  try {
    const response = await submitAsyncForm(form);
    const html = await response.text();
    if (response.ok) {
      if (isFullHtmlDocument(html)) {
        if (reloadOnSuccess) {
          window.location.href = response.url || window.location.href;
        } else if (target) {
          target.innerHTML = renderError("", "Сервер вернул целую страницу вместо фрагмента.", errorTitle);
        }
      } else if (reloadOnSuccess) {
        if (target) {
          target.innerHTML = `<div class="status-box">${escapeHtml(successMessage)}</div>`;
        }
        window.setTimeout(() => window.location.reload(), 450);
      } else if (target) {
        target.innerHTML = html;
      }
    } else if (target) {
      target.innerHTML = renderError(html, errorMessage, errorTitle);
    }
  } catch {
    if (target) {
      target.innerHTML = renderError("", errorMessage, errorTitle);
    }
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = submitLabel;
      button.removeAttribute("aria-busy");
    }
  }
});

function submitAsyncForm(form) {
  const method = (form.dataset.method || form.method || "GET").toUpperCase();
  const action = form.dataset.actionUrl || form.action;
  const headers = { "HX-Request": "true", "Accept": "text/html" };
  if (method === "GET") {
    const url = new URL(action, window.location.origin);
    const params = new URLSearchParams(new FormData(form));
    for (const [key, value] of params.entries()) {
      url.searchParams.set(key, value);
    }
    return fetch(url, { method: "GET", headers });
  }
  return fetch(action, {
    method,
    body: new FormData(form),
    headers,
  });
}

function renderError(rawBody, fallback, title) {
  let message = fallback;
  try {
    const payload = JSON.parse(rawBody);
    if (payload.detail) {
      message = typeof payload.detail === "string" ? payload.detail : fallback;
    }
  } catch {
    if (rawBody && rawBody.length < 500 && !rawBody.includes("<html")) {
      message = rawBody;
    }
  }
  return `<div class="error-box"><strong>${escapeHtml(title)}</strong><p>${escapeHtml(message)}</p></div>`;
}

function isFullHtmlDocument(html) {
  const start = html.trimStart().slice(0, 100).toLowerCase();
  return start.includes("<!doctype html") || start.includes("<html");
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}
