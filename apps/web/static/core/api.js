async function jsonOrThrow(resp) {
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(`${resp.status} ${resp.statusText}: ${body}`);
  }
  return resp.json();
}

export async function fetchMe() {
  return jsonOrThrow(await fetch('/api/me'));
}

export async function postIntake(body, signal) {
  return jsonOrThrow(await fetch('/api/intake', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  }));
}

export async function postValidate(body, signal) {
  return jsonOrThrow(await fetch('/api/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  }));
}

export async function fetchCaoBrief(rlsId) {
  return jsonOrThrow(await fetch(`/api/cao/brief?rlsId=${encodeURIComponent(rlsId)}`));
}

export async function fetchBreakers() {
  return jsonOrThrow(await fetch('/api/health/breakers'));
}
