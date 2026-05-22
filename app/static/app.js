document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.hasAttribute("data-async-form")) {
    return;
  }

  event.preventDefault();
  const targetSelector = form.dataset.target;
  const submitLabel = form.dataset.submitLabel || "Получить ответ";
  const target = targetSelector ? document.querySelector(targetSelector) : null;
  const button = form.querySelector("button[type='submit']");
  const errorMessage = form.dataset.errorMessage || "Запрос не прошел. Проверь сервер и API key.";
  if (button) {
    button.disabled = true;
    button.textContent = "Ищу ответ...";
    button.setAttribute("aria-busy", "true");
  }
  if (target) {
    target.innerHTML = "<div class=\"status-box\">Ищу релевантные фрагменты и готовлю ответ...</div>";
  }

  try {
    const response = await fetch(form.dataset.actionUrl || form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "HX-Request": "true", "Accept": "text/html" },
    });
    const html = await response.text();
    if (target) {
      if (response.ok) {
        target.innerHTML = html;
      } else {
        target.innerHTML = renderError(html, errorMessage);
      }
    }
  } catch {
    if (target) {
      target.innerHTML = renderError("", errorMessage);
    }
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = submitLabel;
      button.removeAttribute("aria-busy");
    }
  }
});

function renderError(rawBody, fallback) {
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
  return `<div class="error-box"><strong>Не удалось получить ответ.</strong><p>${escapeHtml(message)}</p></div>`;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}
