# JourneyBuddy Budget Tracker Knowledge Base

## 1. Budget Tracker Overview

The JourneyBuddy Budget Tracker helps travellers manage travel expenses, define a total travel budget, set a preferred price range, and monitor remaining funds.

The Budget Tracker supports:

- Creating expense records
- Viewing expense records
- Updating expense records
- Deleting expense records
- Setting a total travel budget
- Setting a minimum preferred price
- Setting a maximum preferred price
- Calculating total spending
- Calculating remaining budget
- Providing budget information to the JourneyBuddy AI services


## 2. Budget Definitions

### Total Budget

The total budget is the maximum amount of money that the traveller plans to spend during the trip.

### Total Spent

Total spent is calculated by adding the amount of every recorded expense.

Formula:

Total Spent = Sum of all expense amounts

### Remaining Budget

Remaining budget represents the amount of money still available.

Formula:

Remaining Budget = Total Budget - Total Spent

If total spending exceeds the total budget, the remaining budget becomes negative.

### Minimum Price

The minimum price represents the lower boundary of the traveller's preferred price range.

### Maximum Price

The maximum price represents the upper boundary of the traveller's preferred price range.

The maximum price must be greater than or equal to the minimum price.


## 3. Expense Records

Each expense record contains the following information:

- Expense ID
- Category
- Description
- Amount
- Expense date

The amount of an expense cannot be negative.

An expense requires a category, description, amount, and expense date.


## 4. Expense Categories

Travel expenses may include categories such as:

- Accommodation
- Transport
- Food
- Entertainment
- Shopping
- Activity
- Other

Examples include hotel bookings, flight tickets, train tickets, meals, museum tickets, city tours, and travel accessories.


## 5. Budget Management Guidance

Travellers should compare their total spending with their total budget regularly.

A positive remaining budget means that money is still available.

A remaining budget of zero means that the entire planned budget has been spent.

A negative remaining budget means that spending has exceeded the planned total budget.

Travellers can review individual expense records to identify where money has been spent.


## 6. Preferred Price Range

The minimum and maximum price values represent the traveller's preferred spending range.

The minimum price cannot be negative.

The maximum price must be greater than or equal to the minimum price.

The preferred price range can be used by JourneyBuddy services when evaluating travel-related options.


## 7. Budget Summary

The Budget Tracker provides a budget summary containing:

- Total budget
- Total spent
- Remaining budget
- Minimum price
- Maximum price

The summary is calculated using budget settings and expense records.


## 8. JourneyBuddy MCP Integration

The Budget Tracker is integrated with the JourneyBuddy shared MCP server.

The MCP server provides the following Budget Tracker tools:

### budget_summary

Returns the current Budget Tracker summary.

The result includes:

- Total budget
- Total spent
- Remaining budget
- Minimum price
- Maximum price

### budget_expenses

Returns the current Budget Tracker expense records.

These MCP tools allow JourneyBuddy components to access Budget Tracker information through the shared MCP server.


## 9. RAG Knowledge Boundary

The JourneyBuddy RAG system must answer questions using information available in the approved knowledge base.

If the retrieved knowledge does not contain enough information to answer a question reliably, the system should report that there is insufficient context rather than inventing an answer.

Responses produced from retrieved knowledge should identify the source document used and provide a confidence category.


## 10. Source Information

Document name: JourneyBuddy Budget Tracker Knowledge Base

Knowledge file: budget_tracker.md

Feature owner: Keyuan Gan

Project: JourneyBuddy