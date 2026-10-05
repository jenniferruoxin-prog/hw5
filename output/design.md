# Campus Customs Ops Desk — Dashboard Design

## 1. Design concept

I designed the dashboard as a modern campus print-shop operations desk. It combines a collegiate visual identity with the clarity of an operations dashboard, so it feels like a real workspace rather than a generic admin page.

The primary palette uses deep navy, warm paper, and off-white, with gold for attention and green for completed work. Headings use a campus-inspired serif or varsity-style font, while body text uses a readable sans-serif font such as Inter.

## 2. Layout

The desktop layout has three main areas:

1. **Ticket queue on the left**
   Shows tickets 101, 102, and 103 with their title, status, urgency, and a short issue preview. The database has no priority field, so urgency is a fact from the database instead: the linked invoice or lease due date measured against `desk.date_today` (for example "invoice 501 · 3 days overdue" or "lease 1 rent · due in 2 days"). Open, running, awaiting-approval, and resolved tickets are visually distinct.
2. **Active ticket workspace in the center**
   Shows the selected ticket, its details, the Start Team button, live agent activity, approval requests, and the final summary. This is the main work area and receives the most visual emphasis.

## 3. Operations sidebar on the right

Shows the current checking balance, agent roster, backend connection status, and any action requiring human attention.

On smaller screens, the three areas stack vertically so tickets, agent activity, and approvals remain usable without horizontal scrolling.

## 4. Agent activity

Each agent has a consistent identity so a human can quickly understand who is speaking:

- **Boss:** navy, compass icon
- **Inventory:** blue, box icon
- **Accounting:** green, calculator icon
- **Facilities:** orange, building icon
- **Customer Service:** purple, chat icon

Agent messages appear in a chronological activity timeline. Every entry includes the agent name, status, timestamp, and a label such as `Delegating`, `Checking data`, `Recommendation`, or `Completed`.

Color is not the only distinction: each message also uses a role label and icon for accessibility. A subtle pulse indicates the agent currently working, while completed steps become visually quieter.

## 5. Human approvals

Payment and purchase approvals appear in a prominent amber panel labeled "Human decision required". The panel shows:

- Ticket ID
- Payee or vendor
- Amount
- Reason
- Related invoice, lease, or purchase
- Current checking balance
- Projected balance after approval
- Approve and Reject buttons

The dashboard never describes a proposed payment as completed. A ticket remains `Awaiting approval` until the human acts and the backend confirms the result.

## 6. Resolved tickets

Resolved tickets receive a checkmark and green status treatment and move into a clearly labeled Resolved group, but remain selectable for review.

The selected resolved ticket displays a short summary of what each participating agent did. Agents that were not needed are omitted rather than shown with empty summaries.

A ticket is marked resolved only after the backend reports that the run has finished. A ticket waiting for payment approval is not shown as resolved.

## 7. Checking balance

The checking balance remains visible in the operations sidebar. It is retrieved from the backend rather than calculated independently in the browser.

After an approved payment, the dashboard refreshes the balance and briefly highlights the change. It shows the previous balance, payment amount, and updated balance so the human can understand why cash changed.

The interface warns the user when a proposed payment would exceed available cash, but the backend remains responsible for refusing a payment that would create a negative balance.

## 8. Motion and feedback

Motion is subtle and functional:

- New agent activity fades into the timeline.
- The active agent has a small working indicator.
- Ticket status changes animate briefly.
- The cash card highlights after a confirmed payment.
- Approval success and failure appear as clear toast messages.

The dashboard respects `prefers-reduced-motion`, so users can disable nonessential animation.

## 9. Creative details

To make the dashboard feel specific to Campus Customs, ticket cards resemble clean print-shop job slips rather than generic software cards. Small paper, ink, package, and storefront details reinforce the shop identity without reducing readability.

The selected ticket area is called the **Workbench**, the ticket list is the **Desk Queue**, and the agent activity area is the **Team Feed**. These names make the interface feel like a coordinated shop workspace while remaining easy to understand.

## 10. Why this design helps

The layout keeps the ticket, agent reasoning, human approval, and financial impact visible at the same time. A user can quickly answer:

- What needs attention?
- Which agent is working?
- What has already been verified?
- Is human approval required?
- Did the payment affect cash?
- Is the ticket truly resolved?

The design makes agent activity transparent without overwhelming the user, keeps risky financial actions clearly separated from ordinary updates, and gives Campus Customs a recognizable, enjoyable storefront identity.

## 11. Backend connection

The frontend sends API requests to:

`http://localhost:8000`

The backend allows requests from the Vite development origin:

`http://localhost:5173`

The frontend is started from the `frontend/` directory with:

`npm run dev`
