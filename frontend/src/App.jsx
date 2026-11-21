import { useEffect, useState } from 'react';

const TICKETS_URL = '/api/tickets';
const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
});

function TicketList({ tickets, loadFailed, onRetry }) {
  return (
    <section className="panel" aria-labelledby="tickets-heading">
      <div className="panel-heading">
        <h2 id="tickets-heading">Tickets</h2>
        {tickets && <span className="ticket-count">{tickets.length} total</span>}
      </div>
      {loadFailed ? (
        <div className="queue-message">
          <p role="alert">Couldn’t load the ticket queue.</p>
          <button className="secondary-button" type="button" onClick={onRetry}>
            Try again
          </button>
        </div>
      ) : tickets === null ? (
        <p className="queue-message" role="status">Loading tickets…</p>
      ) : tickets.length === 0 ? (
        <p className="queue-message">No tickets yet.</p>
      ) : (
        <ul className="ticket-list" role="list">
          {tickets.map((ticket) => (
            <li className="ticket" key={ticket.id}>
              <div className="ticket-heading">
                <h3>{ticket.subject}</h3>
                <span className="ticket-status" data-status={ticket.status}>
                  {ticket.status === 'open' ? 'Open' : 'Resolved'}
                </span>
              </div>
              <p className="ticket-description">{ticket.description}</p>
              <p className="ticket-meta">
                <span>#{ticket.id}</span>
                <time dateTime={ticket.created_at}>
                  {dateFormatter.format(new Date(ticket.created_at))}
                </time>
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function TicketForm({ disabled, onCreated }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function submitTicket(event) {
    event.preventDefault();
    setError('');
    setNotice('');

    const form = event.currentTarget;
    const fields = new FormData(form);
    const subject = fields.get('subject').trim();
    const description = fields.get('description').trim();
    if (!subject || !description) {
      setError('Enter a subject and a description.');
      form.elements[!subject ? 'subject' : 'description'].focus();
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(TICKETS_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject, description }),
      });
      if (!response.ok) throw new Error('Ticket could not be created');

      const ticket = await response.json();
      onCreated(ticket);
      form.reset();
      setNotice(`Ticket #${ticket.id} created.`);
    } catch {
      setError('Couldn’t create the ticket. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="new-ticket-heading">
      <div className="panel-heading">
        <h2 id="new-ticket-heading">New ticket</h2>
      </div>
      <form className="ticket-form" onSubmit={submitTicket}>
        <fieldset disabled={saving}>
          <div className="field">
            <label htmlFor="subject">Subject</label>
            <input id="subject" name="subject" required maxLength={120} />
          </div>
          <div className="field">
            <label htmlFor="description">Description</label>
            <textarea id="description" name="description" required maxLength={2000} rows={5} />
          </div>
          <button type="submit" disabled={disabled || saving}>
            {saving ? 'Creating…' : 'Create ticket'}
          </button>
        </fieldset>
        <p className="form-error" role="alert">{error}</p>
        <p className="form-notice" role="status">{notice}</p>
      </form>
    </section>
  );
}

export default function App() {
  const [tickets, setTickets] = useState(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function loadTickets() {
      try {
        const response = await fetch(TICKETS_URL, { signal: controller.signal });
        if (!response.ok) throw new Error('Ticket queue could not be loaded');
        const loadedTickets = await response.json();
        if (!controller.signal.aborted) setTickets(loadedTickets);
      } catch {
        if (!controller.signal.aborted) setLoadFailed(true);
      }
    }

    loadTickets();
    return () => controller.abort();
  }, [loadAttempt]);

  function retryLoad() {
    setLoadFailed(false);
    setLoadAttempt((attempt) => attempt + 1);
  }

  function addTicket(ticket) {
    setTickets((current) => [ticket, ...current]);
  }

  return (
    <>
      <header className="page-header">
        <div className="page-width">
          <h1>Support ticket queue</h1>
        </div>
      </header>
      <main className="page-width layout">
        <TicketList tickets={tickets} loadFailed={loadFailed} onRetry={retryLoad} />
        <TicketForm disabled={tickets === null} onCreated={addTicket} />
      </main>
    </>
  );
}
