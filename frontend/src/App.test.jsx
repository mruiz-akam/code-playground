import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import App from './App.jsx';

const openTicket = {
  id: 1,
  subject: 'Reports time out',
  description: 'The Reports page stopped loading.',
  status: 'open',
  created_at: '2026-11-20T15:00:00Z',
};

const resolvedTicket = {
  ...openTicket,
  id: 2,
  subject: 'Update the billing address',
  description: 'The new billing address is on file.',
  status: 'resolved',
};

const fetchMock = vi.fn();

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test('loads the queue and displays each ticket status', async () => {
  fetchMock.mockResolvedValueOnce(jsonResponse([resolvedTicket, openTicket]));

  render(<App />);

  expect(screen.getByText('Loading tickets…')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Create ticket' }).disabled).toBe(true);

  const [first, second] = await screen.findAllByRole('listitem');
  expect(within(first).getByRole('heading', { name: resolvedTicket.subject })).toBeTruthy();
  expect(within(first).getByText('Resolved')).toBeTruthy();
  expect(within(second).getByRole('heading', { name: openTicket.subject })).toBeTruthy();
  expect(within(second).getByText('Open')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Create ticket' }).disabled).toBe(false);
  expect(fetchMock).toHaveBeenCalledWith('/api/tickets', expect.any(Object));
});

test('retries a failed queue request and shows the empty state', async () => {
  const user = userEvent.setup();
  fetchMock
    .mockResolvedValueOnce(jsonResponse({}, 503))
    .mockResolvedValueOnce(jsonResponse([]));

  render(<App />);

  expect(await screen.findByText('Couldn’t load the ticket queue.')).toBeTruthy();
  await user.click(screen.getByRole('button', { name: 'Try again' }));

  expect(await screen.findByText('No tickets yet.')).toBeTruthy();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test('creates a ticket, adds it to the queue, and clears the form', async () => {
  const user = userEvent.setup();
  const newTicket = {
    ...openTicket,
    id: 3,
    subject: 'Missing report',
    description: 'The export was empty.',
  };
  fetchMock
    .mockResolvedValueOnce(jsonResponse([openTicket]))
    .mockResolvedValueOnce(jsonResponse(newTicket, 201));

  render(<App />);
  await screen.findByRole('heading', { name: openTicket.subject });

  const subject = screen.getByRole('textbox', { name: 'Subject' });
  const description = screen.getByRole('textbox', { name: 'Description' });
  await user.type(subject, `  ${newTicket.subject}  `);
  await user.type(description, newTicket.description);
  await user.click(screen.getByRole('button', { name: 'Create ticket' }));

  expect(await screen.findByText('Ticket #3 created.')).toBeTruthy();
  const [first] = screen.getAllByRole('listitem');
  expect(within(first).getByRole('heading', { name: newTicket.subject })).toBeTruthy();
  expect(subject.value).toBe('');
  expect(description.value).toBe('');
  expect(fetchMock).toHaveBeenLastCalledWith('/api/tickets', expect.objectContaining({
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  }));
  expect(JSON.parse(fetchMock.mock.lastCall[1].body)).toEqual({
    subject: newTicket.subject,
    description: newTicket.description,
  });
});

test('keeps the form values when ticket creation fails', async () => {
  const user = userEvent.setup();
  fetchMock
    .mockResolvedValueOnce(jsonResponse([]))
    .mockResolvedValueOnce(jsonResponse({}, 500));

  render(<App />);
  await screen.findByText('No tickets yet.');

  const subject = screen.getByRole('textbox', { name: 'Subject' });
  const description = screen.getByRole('textbox', { name: 'Description' });
  await user.type(subject, 'Export failed');
  await user.type(description, 'The file is empty.');
  await user.click(screen.getByRole('button', { name: 'Create ticket' }));

  expect(await screen.findByText('Couldn’t create the ticket. Please try again.')).toBeTruthy();
  expect(screen.getByText('No tickets yet.')).toBeTruthy();
  expect(subject.value).toBe('Export failed');
  expect(description.value).toBe('The file is empty.');
  expect(screen.getByRole('button', { name: 'Create ticket' }).disabled).toBe(false);
});

test('rejects whitespace-only input before sending a create request', async () => {
  const user = userEvent.setup();
  fetchMock.mockResolvedValueOnce(jsonResponse([]));

  render(<App />);
  await screen.findByText('No tickets yet.');

  const subject = screen.getByRole('textbox', { name: 'Subject' });
  await user.type(subject, '   ');
  await user.type(screen.getByRole('textbox', { name: 'Description' }), 'Report details');
  await user.click(screen.getByRole('button', { name: 'Create ticket' }));

  expect(screen.getByText('Enter a subject and a description.')).toBeTruthy();
  expect(document.activeElement).toBe(subject);
  expect(fetchMock).toHaveBeenCalledTimes(1);
});
