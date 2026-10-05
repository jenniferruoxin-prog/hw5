# HW5 AI Prompt Log

This log records the prompts I typed to my AI coding assistant while completing Homework 5. Each problem has its own section, so the work can be reviewed problem by problem. Each section includes the problem number and title, at least one prompt I typed, and a follow-up prompt only if I actually needed one.

## Problem 1 — Create and maintain the AI_prompts.md log

### Prompts typed

> Today we will work on Homework 5. Put everything in that folder similar to what we did in Homework 4. I will give you instructions also the way in Homework 4

> Now we work on problem 1. I need you to create AI_prompts.md at the start of the assignment and keep it updated as we work.This file is the log of what I typed to you. Put one section for each problem. Each section must include:
> The problem number and title
>  At least one prompt I typed
>  One follow-up prompt, only if I actually needed it and typed it

## Problem 2 — Shop database, working copy and harness.md

### Prompt typed

> Now we work on problem 2. I want you to have the context of what we are doing. Campus Customs Multi-Agent Operations is the agentic team that runs the shop. Opentickets land on a board - customer orders, rent, unpaid bills, discount requests, whateverthe shop has to handle. I will build three pieces that talk to each other: an MCP server, aFastAPI backend with a multi-agent team, and a React dashboard so a human can watchthe agents at work and approve requests.
> My agent team has full connectivity - any agent may delegate tasks to any other agent for help. In this assignment you will build these agents:
>
> 1. Boss - reads each ticket, decides who should work on it, and makes final calls
> 2. Inventory - checks stock by SKU and size, spots shortfalls, and figures out which vendor can restock
> 3. Accounting - watches cash and invoices, checks margins, and prepares payments or purchase orders for human approvalCustomer Service - drafts messages for customers
>
> Facilities - handles the shop space side (leases, rent, etc.)  5. Customer Service - drafts messages for 
> You will find that I already downloaded data.zip. Unzip so we have data/campus_customs.db. That file is the original shop database. Tables include desk, tickets, inventory, pricing, vendors, Leases, cash_accounts, payments and invoices
> Your tools will update the database as tickets get resolved. Make a copy of the database file calleddata/campus_customs_new.db and point our MCP server and backend at that working copy. Keep campus_customs.db untouched so you can reset when you want to restart resolving the tickets. The field desk.date_today is "today" for the shop. Use this date to determine what is overdue. Vendor lead times come from the vendors table. A vendor will not ship new product while they still have an open unpaid invoice
> Human approval is required for any payments. Points will be deducted if this is not done. If payment is made, make sure to update the relevant table.
> If there is not enough cash, the pay tool must refuse - no negative balances Cash only goes out in this homework - we did not model revenue, so no money comes in. Before a full run to resolve the tickets, make sure to reset the database to the original values.
> DO NOT email customers or call real vendors. Drafts stay on the board
> Use our PORTKEY_API_KEY for Al calls. For this assignment, USE ONLY gpt-6-luna through Portkey for every agent!!!!!!!!! Multi-agent chats burn tokens fast so I only want to use luna. I will be angry if any other model shows up in your code or runs. Check if you used other models in the problem 1 actually. if you did, delete anything you've done,and  redo problem 1 with luna.
> Final submission will be a public GitHub repo just like HW 4. Okay now that you know the context, Open data/campus_customs.db and look through every table and its fields. Copy the original file to data/campus_customs_new.db- later problems update that working copy. Study the three open tickets so you see how they link to other tables. And then, start output/harness.md. For each table, list the fields and one short line on why that table matters for the agents. We will keep growing this harness file in later problems.

### Follow-up prompt

> only use gpt-6-luna. what do you mean by every call will fail? do I need to do anything to get the gpt-6-luna work?

## Problem 3 — MCP server with three ticket tools

### Prompt typed

> Now we work on problem 3. Write an MCP server in mcp_server/ using FastMCP. It will talk to data/campus_customs_new.db. We do NOT need to connect or run it in this problem. 
> Every agent in this homework uses the tools in this MCP server. I will add more tools toit later; for now write three tools we know we will need for the tickets in the database. Keep the names clear. Never invent any data, only use information in the database. In output/harness.md, list each of our three MCP tools. For every tool include: which table it reads, which ticket it helps unlock (101, 102, or 103), and one sentence(only one!) on why that tool is the right one for that ticket. Really tie the tool to the ticket. Vague lines like "reads inventory" should not be written. Then, also add a short mcp_server/README.md file that explains what the MCP server is for, which database file it uses, and the three tools it has

## Problem 4 — Connect the MCP server to the vibe coder and smoke-test the tools

### Prompt typed

> Now we work on problem 4. Add our MCP server to this project so you, as a vibe coder, can call the tools. Save the connection JSON text in .mcp.json at the project root (or however you, the vibe coder,saves local MCP server lists). With the vibe coder connected, I want to test each of our three MCP tools. save the evidence in output/mcp_smoke.json. For every tool include: the prompt I asked you (the vibe coder), the tool name, the tool output (must match values in data/campus_customs_new.db). Now, the prompts I ask you are going to be: First, use the Campus Customs MCP tool `check_vendor_shipping` to check whether Bulldog Print Co is currently eligible to ship a restock for the size S tee in ticket 101. Use the shop date from the database. Return the MCP tool output exactly as received, without adding or inferring any information. Do not update the database. Second, use the Campus Customs MCP tool `get_rent_due` to retrieve the rent obligation owed to Elm City Properties for ticket 102. Determine its status using `desk.date_today`. Return the MCP tool output exactly as received, without adding or inferring any information. Do not create a payment and do not update the database. Third, use the Campus Customs MCP tool `check_stock_and_price` to check the inventory and pricing information for the size M hoodie referenced in ticket 103. Return the quantity on hand, unit cost, and list price exactly as returned by the tool. Do not calculate or recommend a discount, and do not update the database.

### Follow-up prompts

> go

> We continue working on problem 4. Using the three MCP tool calls we just completed, create `output/mcp_smoke.json`.
> For each tool call, record my exact prompt, the exact MCP tool name, and the complete unmodified tool output. Associate each test with its corresponding ticket ID: 101, 102, or 103.
> Preserve all field names, values, numbers, dates, booleans, and nulls exactly as returned by the MCP tools. Do not summarize, reinterpret, or invent any information. Do not rerun the tools and do not update the database.
> Make sure the result is valid JSON, save it at `output/mcp_smoke.json`, and then confirm the saved path.

## Problem 5 — PydanticAI agent team (Boss, Inventory, Accounting, Facilities, Customer Service)

### Prompt typed

> Now on problem 5. Build the agentic team for Campus Customs using PydanticAl: Boss, Inventory, Accounting, Facilities, and Customer Service. Include prompts, models, and agent loops so they can delegate work to each other with full connectivity. 
> Put the agent prompts in backend/prompts, one file per agent. Put data types inbackend/models.py and the agent files under backend/ (layout can vary as long as the five roles are clear). Use our PORTKEY_API_KEY and only gpt-6-luna for every agent.
> Write each prompt in your own words with the shop rules that agent needs. More detailedprompts that cover all aspects of an agent's work and scope score higher than a short generic prompt. For the prompts, I'm thinking about what to write right now. just tell me you understand what we are doing and I will send the prompts with the shop rules that agent needs.

> still on problem 5. For the rules, include (1 )shared rules: You are part of the Campus Customs operations team. Use only verified information from approved tools, the working database, or another agent. Never invent values or completed actions. Use data/campus_customs_new.db. Never modify the original campus_customs.db. Use desk.date_today as today's date. Any agent may delegate a specific subtask to another agent. Include the ticket ID and relevant facts, avoid repeated work and circular delegation, and return findings to the Boss. Every payment requires human approval. Never allow a negative cash balance. This homework models cash outflows only. Do not contact customers or vendors. Communications remain drafts on the board. Never claim that an action occurred unless its tool succeeded. Use only gpt-6-luna through Portkey, with no model fallback. Delegate only a specific unanswered question. Include the ticket ID and verified context. Do not return a task to the agent that just delegated it unless new information creates a different question. If the answer remains unavailable, report the limitation to the Boss. (2)Boss: You are the Boss. Read each ticket, delegate work, combine verified findings, and make the final decision. Send inventory and vendor issues to Inventory; invoices, cash, margins, discounts, and payments to Accounting; rent and leases to Facilities; and customer drafts to Customer Service. Use multiple agents when a ticket crosses functions. Do not invent missing facts or override tool-backed results. If agents disagree, ask them to verify the relevant records. Every payment requires human approval. A ticket involving payment should remain awaiting approval until the approved payment succeeds. Close a ticket only when required actions are completed. Clearly distinguish recommended, awaiting approval, executed, refused, and resolved actions. (3) Inventory: You are the Inventory agent. Check stock, SKUs, sizes, shortfalls, vendors, and lead times. Use exact database values. Calculate shortfall as requested quantity minus quantity on hand. Use vendor lead times from the vendors table. A vendor cannot ship while it has an open unpaid invoice. If blocked, report the invoice and ask Accounting to review it. Do not order products, adjust inventory, approve payment, or contact vendors unless an authorized tool and workflow permit it. Return verified findings and a recommendation to the Boss. (4) Accounting: You are the Accounting agent. Review cash, invoices, payments, costs, prices, margins, discounts, and purchase or payment proposals. Before proposing payment, verify the payee, amount, reference, due date, payment status, available cash, and projected balance. Use desk.date_today and check for duplicate payments. Every payment requires explicit human approval. Refuse any payment that would make cash negative. Do not assume incoming revenue. After an approved payment succeeds, verify that cash, payment, and invoice records were updated. For discounts, report cost, list price, proposed price, and margin, and flag prices below cost. (5)facilities: You are the Facilities agent. Handle leases, rent, landlords, and shop-space obligations. Read lease terms from the database and use desk.date_today to determine whether rent is upcoming, due, or overdue. Do not pay rent or contact the landlord. Send verified payment details to Accounting and the Boss. All payments require human approval and sufficient cash. Report missing, expired, overdue, or inconsistent lease information. (6) Customer service: You are the Customer Service agent. Draft accurate, professional customer messages using only verified information. Do not send messages. Keep every communication as a draft on the board. Do not promise stock, delivery dates, discounts, orders, or payments unless verified. Ask Inventory, Accounting, or Facilities for missing facts and ask the Boss for final decisions. Do not reveal internal cash balances, invoice disputes, or private business information. Clearly label each message as a draft.

### Follow-up prompts

> Oh sorry by "write prompts in your own words" I made a mistake. I meant the prompts should be in my own words, not yours.

> Still on problem 5. Add any tools the agents need to the MCP server so they can work on the open tickets. Shop facts come from the MCP server over data/campus_customs_new.db-do not inventa second shop-tools layer that bypasses MCP. 
> Wire the agents so they append to output/audit_trail.json as they run: for each agent loop step, record enough to audit later. Append to this file - do not wipe it each run. In output/harness.md, list each agent and each MCP tool (including ones you add in this output) along with which table the tool uses. Also add a short safety section: the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check. Update mcp_server/README.md so the tool list matches what we have now.

## Problem 6 — Expected plan per ticket (output/desk_tickets.html)

### Prompt typed

> now on to problem 6. Before you wire the backend, write down what you expect the team to do on each openticket. Build output/desk_tickets.html, a page I can double-click with one tab per ticket (101, 102, and 103).  Also add empty Cash and Reflection tabs for later problems (leave them blank or with a short "coming later" note for now).
> On each ticket tab, fill an Expected section only (leave room for an Actual section we will fill after we run the agents). For each ticket's Expected section, I will write 
> (1)Who the Boss should call first, and why 
> (2)All the agent delegations you expect - not "Boss calls everyone"； (3)  Which McP tools you expect that run to use
> We will compare this plan to what actually happens when our agents resolve the three tickets. If you understand, I'm going to give you the expected section for each ticket tab one by one.

### Follow-up prompts

> Ticket 101 Expected
> a) Who the Boss should call first, and why
> Inventory first. Ticket 101 begins with an out-of-stock size S tee and a possible vendor restock, so Inventory should verify the vendor's shipping eligibility and identify anything blocking replenishment.
>
> b) Expected agent delegations
> 1. The Boss delegates ticket 101 to Inventory to investigate the size S tee shortage and the vendor's ability to restock it.
> 2. Inventory delegates the unpaid-invoice issue to Accounting after confirming that Bulldog Print Co. is blocked from shipping.
> 3. Accounting checks whether invoice 501 can be paid, prepares a payment request, and returns it to the Boss for human approval. Accounting must not make the payment without approval.
> 4. If payment is approved and completed, Inventory rechecks whether the vendor is eligible to ship.
> 5. After the Boss decides the next step, the Boss delegates to Customer Service to draft a customer update. The draft must not promise a restock date unless Inventory has verified one. c)check_vendor_shipping — checks whether Bulldog Print Co. can ship and identifies the unpaid invoice blocking the restock.  
> The run may call it again after an approved payment to confirm that the vendor is no longer blocked.

> Yes, please add all six of those tools to Ticket 101 part (c), in addition to `check_vendor_shipping`, because they follow directly from the expected delegation plan.
> The expected tools for Ticket 101 should be:
> - `check_stock_and_price` — Inventory verifies that the size S tee is out of stock.
> - `check_vendor_shipping` — Inventory checks whether Bulldog Print Co. can ship and identifies the unpaid invoice blocking the restock.
> - `get_invoice` — Accounting verifies invoice 501, its amount, due status, and whether it has already been paid.
> - `get_cash_balance` — Accounting checks whether the shop has enough cash to cover the invoice without creating a negative balance.
> - `request_payment_approval` — Accounting creates a pending human-approval request for the $840 payment.
> - `save_draft` — Customer Service saves the customer update as a draft without sending it.
> - `update_ticket_status` — the Boss changes ticket 101 to `awaiting_approval`.
> Do not include a payment-execution tool or an inventory-update tool in the Expected section yet, because the initial run should stop and wait for human approval.

> Ticket 102 Expected
> a) Who the Boss should call first, and why
> Facilities first. Ticket 102 concerns rent, a landlord, and a lease due date, so Facilities should verify the lease obligation and determine whether the rent is upcoming, due, or overdue using the shop date.
> b). Expected agent delegations
> 1. The Boss delegates ticket 102 to Facilities to verify the landlord, rent amount, due date, and payment status.
> 2. Facilities delegates the verified rent obligation to Accounting because paying rent affects cash and requires approval.
> 3. Accounting checks available cash, checks for a duplicate payment, calculates the projected balance, and returns a payment request to the Boss.
> 4. The Boss pauses the ticket for human approval. Payment must not occur before approval.
> 5. If approved, Accounting executes and verifies the payment before the Boss closes the ticket. c). Expected MCP tools
> - get_rent_due — retrieves the rent owed to Elm City Properties and evaluates the due date using desk.date_today.

> yeah please make both changes to suit it better to our system

> Ticket 103 Expected
> a) Who the Boss should call first, and why
> Inventory first. Before considering the discount request, the team must verify whether 20 size M hoodies are available and retrieve the product's cost and list price.
> b) Expected agent delegations
> 1. The Boss delegates ticket 103 to Inventory to verify the quantity on hand, calculate the shortfall, and retrieve the hoodie's cost and list price.
> 2. Inventory delegates the verified pricing information to Accounting to evaluate the requested discount and calculate the resulting dollar and percentage margins.
> 3. Accounting returns the margin analysis to the Boss and flags any price below cost or otherwise unacceptable margin. Accounting does not make the final customer decision.
> 4. The Boss decides whether to approve, reject, or revise the discount and determines how to handle the inventory shortfall.
> 5. The Boss delegates the final verified decision to Customer Service, which drafts—but does not send—the customer response.
> c) Expected MCP tools
> - check_stock_and_price — returns the size M hoodie's quantity on hand, unit cost, and list price so Inventory can identify the shortfall and Accounting can evaluate the discount.

> yes please add

## Problem 7 — FastAPI backend routes for the dashboard

### Prompt typed

> Now on to problem 7. Our react frontend dashboard (the next problem) needs a backend it can call. In backend/main.py use FastAPI and add routes that do the following: 
> Return the three tickets and whether each is open or resolved
> Take a ticket id and run your agent team on that ticket
> Return recent agent events - what each agent said and which tools they used - so the board can refresh
> Approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash)
> Return the current checking balance from cash_accounts
> Reset the database to the original values when you want to try a fresh run. From the backend/ folder, start the server with uvicorn main:app --reload --port 8000. This turns on your backend at http://localhost:8000so the frontend dashboard can callthose routes.IIn output/harness.md list each route in one line (what URL / what it does).

## Problem 8 — React + Vite + TypeScript dashboard (the Ops Desk)

### Prompt typed

> Now we work on problem 8. Build the frontend dashboard in frontend/ with React + Vite + TypeScript. The page should call the routes I built in Problem 7. At minimum the board should: 
> 1)List all three tickets
> 2) Let me pick one ticket and start the agent team on it
> 3) Show each agent and what they are saying / doing while the ticket runs
> 4) Mark a ticket resolved when the run finishes
> 5) Show a short summary of what each agent did on that ticket
> 6) Let a human approve a pay or purchase when asked
> 7) Show the checking balance (it should drop after an approved pay)
> Make the dashboard look good. Be creative with the layout and feel - this is a real desk people would want to sit at, so put thought into how it looks. Tell the front end to talk to your backend at http://localhost:8000. On the backend, allow the Vite page origin (usually http://localhost:5173) so the browser is allowed to call those routes. Start the board with: npm run dev
> This opens the React desk in my browser so I can pick tickets and watch agents.
> Then I will tell you to write output/design.md with what I chose for the dashboard look (layout, how agentsread differently, how resolved tickets and cash show up) and why - including the creative choices that make it feel special and something humans would actually enjoy using. I'm still thinking about what to write now and I will tell you later.\

### Follow-up prompt

> you can keep the appendix

> For the content in output/design.md, I want to write 1)Design concept … 11) Backend connection (the full text I pasted is saved word for word in output/design.md).

> sure, update

## Problem 9 — Full run: resolve all three tickets, cash, resolved board, finish the harness

### Prompt typed

> Now we work on problem 9. Before testing the agents on a full run over the three tickets, reset the working database data/campus_customs_new.db again so we start clean. Note the starting checking balance. Then run all three tickets on the board (101, 102, 103) until each is resolved. Open output/desk_tickets.html from Problem 6. On each ticket tab, fill the Actual section from this run: which agents worked, what they delegated, and which tools they used. Keep our Expected section so we can compare the two. On the Cash tab of the same output/desk_tickets.html, itemize the money: 
>  Starting checking balance (after the reset)purchase, dollar amount)
>  For each ticket: how cash changed when that ticket resolved, and why (which pay /
>  Ending checking balance - it must match cash_accounts in the working database
> Wrong cash math loses points even if the board shows every ticket resolved. Also save:
> - output/resolved_tickets.json, so for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals
> -output/resolved_board.html, a page you can double-click with a screenshot of your
> React board for each resolved ticket (101, 102, and 103)
> Append real runs to output/audit_trail.json. Finish output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.

### Follow-up prompts

> I approve payment requests 1 and 2 as Jennifer Zhang. Use the local homework approval route only and confirm that this updates only data/campus_customs_new.db. Do not contact any external payment service, customer, landlord, or vendor. After approval, verify the payment records and cash balance, then rerun tickets 101 and 102 so the agents can determine whether they should be resolved. Do not approve or create any additional payment without asking me first.

> I approve as jennifer zhang, and yes rerun it

> Ticket 101: Treat the ticket as complete once the tee order is placed and paid, its September 5 expected arrival is recorded, and the customer draft is saved. Do not claim it has arrived or contact the customer.
> Ticket 103: Offer only the 8 in-stock hoodies at a 10% discount ($52.20 each). Do not restock the remaining 12 or approve another purchase. Save, but do not send, a customer draft.

> yes add that and rerun 103

## Problem 10 — Reflection tab in output/desk_tickets.html

### Prompt typed

> Now we work on problem 10. Open output/desk_tickets.html and fill the Reflection tab. Answer in your own vibe, and be detailed and thorough:
> --How would you evaluate the performance of the agents on each ticket and why?
> --For each ticket, how did Actual compare to the Expected plan you wrote earlier?
> --What would have been simpler as one agent with tools - and why?
> --Describe three new problems Campus Customs might face that this agent team could solve with the tools you built
> --Describe three new problems Campus Customs might face that this agent team could notsolve with the tools you built, and explain the tools and agents you would need to solve them. Tie every answer to this app and the three tickets you ran - use the ticket tabs and Cashtab on the same page as your evidence. Generic Al essays without Campus Customs details will score low. So below is what I'm thinking, and you can add more to tie it to the specific details or correct me if I'm wrong. Reflection
> 1. How I evaluate the agents' performance … 5. Three new problems the current team could not solve … Overall assessment (my full draft: Ticket 101/102/103 evaluations, Actual vs Expected per ticket, Ticket 102 as the one-agent case, solvable problems A–C, unsolvable problems A–C: receiving shipments, discount policy, recording sales/refunds/cash inflows). The draft is kept in my voice in the Reflection tab, with facts corrected to the final run.

## Problem 11 — Public GitHub repo, README and output/github_url.txt

### Prompt typed

> Now on problem 11. Push tmy code to a public GitHub repository so graders can clone it. I will need the repo URL, and also put it inoutput/github_url.txt.
> Do not push my real .env to the GitHub repo. Do include both database files under data/(the original and my working copy) so graders can run your app easily.
> Expected file layout showed in the picture. README should explain: copy original DB to the working copy when you need a clean run,start MCP server, start FastAPI backend, start the React board, reset the DB before a full three-ticket run.

### Follow-up prompts

> why are there two folders in output/

> yes I want it to match my layout picture exactly.

> sure leave it

> do not match the picture if it messes up with the code
