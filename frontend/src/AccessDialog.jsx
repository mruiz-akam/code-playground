import { useState } from 'react';

export default function AccessDialog({ allowHttp, onAccess }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const canEnterToken = allowHttp || window.location.protocol === 'https:';

  async function submit(event) {
    event.preventDefault();
    if (!canEnterToken || pending) return;

    const token = new FormData(event.currentTarget).get('token');
    setPending(true);
    setError('');
    try {
      const response = await fetch('/api/access', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });

      if (response.ok) {
        onAccess();
      } else if (response.status === 401) {
        setError('That access token is incorrect.');
      } else if (response.status === 403) {
        setError('Open the lab URL provided by your interviewer and try again.');
      } else {
        setError('Couldn’t check the access token. Please try again.');
      }
    } catch {
      setError('Couldn’t check the access token. Please try again.');
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="page-width access-layout">
      <section className="panel" role="dialog" aria-labelledby="access-heading">
        <div className="panel-heading">
          <h2 id="access-heading">Enter your access token</h2>
        </div>
        {canEnterToken ? (
          <form className="ticket-form" onSubmit={submit}>
            <fieldset disabled={pending}>
              <div className="field">
                <label htmlFor="access-token">Access token</label>
                <input id="access-token" name="token" type="password" required autoFocus />
              </div>
              <button type="submit">{pending ? 'Checking…' : 'Open queue'}</button>
            </fieldset>
            <p className="form-error" role="alert">{error}</p>
          </form>
        ) : (
          <p className="queue-message">
            <a href={`https://${window.location.host}/`}>Open the lab over HTTPS</a> to enter your token.
          </p>
        )}
      </section>
    </main>
  );
}
