const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function parseResponse(response) {
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

export async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  let body = options.body;

  if (body && !(body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    body,
  });

  const payload = await parseResponse(response);
  if (!response.ok) {
    const message = payload?.error || payload?.detail || 'Request failed';
    throw new Error(message);
  }
  return payload;
}

export function upload(path, formData) {
  return request(path, {
    method: 'POST',
    body: formData,
  });
}
