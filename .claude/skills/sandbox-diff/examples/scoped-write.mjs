// Skeleton: scoped sandbox writes for one allowlisted test account and one resource kind.
// Copy into the project's harness scripts folder and fill the constants and the vendor calls.
// Run from the backend checkout so credentials stay in the process: node --env-file=.env scoped-write.mjs <mode> [args]
//   show                 read-only: list this account's records of the scoped resource
//   create <variant>     create one record on the scoped resource for the test account
//   flag <recordId>      change one existing record, only if it belongs to the test account and resource
// Log every write in the project's write log right after it runs.

const SANDBOX_HOST = 'sandbox.vendor.example';
const TEST_ACCOUNT = '<allowlisted test account id>';
const RESOURCE = process.env.VENDOR_SCOPED_RESOURCE_ID;
const base = process.env.VENDOR_API_BASE_URL;

console.error(`host: ${base ? new URL(base).host : '(none)'}`);
if (!base || new URL(base).host !== SANDBOX_HOST) throw new Error('not the sandbox host');
if (!RESOURCE) throw new Error('VENDOR_SCOPED_RESOURCE_ID missing');

const [mode, arg] = process.argv.slice(2);

const call = async (path, init = {}) => {
  const res = await fetch(`${base}${path}`, init);
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(`${init.method ?? 'GET'} ${path.split('?')[0]} failed: HTTP ${res.status}`);
  return body;
};

// Replace with the vendor's auth flow. Never print the token or the secrets.
const headers = {
  Authorization: `Bearer ${process.env.VENDOR_API_TOKEN}`,
  'Content-Type': 'application/json',
};
const post = (path, body) => call(path, { method: 'POST', headers, body: JSON.stringify(body) });

const mine = async () => {
  const page = await call(`/records?resource=${RESOURCE}&account=${TEST_ACCOUNT}&limit=100`, { headers });
  return (page.data ?? []).filter((r) => r.account === TEST_ACCOUNT && r.resource === RESOURCE);
};

const summary = (r) => ({ id: r.id, status: r.status, created_at: r.created_at });

if (mode === 'show') {
  for (const r of await mine()) console.log(JSON.stringify(summary(r)));
} else if (mode === 'create') {
  const created = await post('/records', { resource: RESOURCE, account: TEST_ACCOUNT, variant: arg });
  if (created.account !== TEST_ACCOUNT || created.resource !== RESOURCE) {
    throw new Error(`created record ${created.id} is not the scoped one: stop and log it`);
  }
  console.log(JSON.stringify({ created: summary(created) }));
} else if (mode === 'flag') {
  if (!(await mine()).some((r) => r.id === arg)) throw new Error('not one of the test account records');
  await post(`/records/${arg}`, { flagged: true });
  console.log(JSON.stringify({ flagged: arg }));
} else {
  throw new Error('mode: show | create <variant> | flag <recordId>');
}
