export async function apiRequest(path, options = {}) {
  const config = {
    method: options.method || 'GET',
    headers: { ...(options.headers || {}) },
  }

  if (options.body !== undefined) {
    config.headers['Content-Type'] = 'application/json'
    config.body = JSON.stringify(options.body)
  }

  const response = await fetch(path, config)
  const text = await response.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }

  if (!response.ok) {
    const message =
      (payload && (payload.detail || payload.error || payload.message)) ||
      `HTTP ${response.status}`
    throw new Error(message)
  }

  return payload
}

export function apiGet(path) {
  return apiRequest(path)
}

export function apiPost(path, body) {
  return apiRequest(path, { method: 'POST', body })
}

export function apiPatch(path, body) {
  return apiRequest(path, { method: 'PATCH', body })
}

export function apiPut(path, body) {
  return apiRequest(path, { method: 'PUT', body })
}

export function apiDelete(path) {
  return apiRequest(path, { method: 'DELETE' })
}
