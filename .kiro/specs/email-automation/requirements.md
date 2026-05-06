# Requirements Document

## Introduction

This feature adds automated email sending capabilities to the Supply Chain Disruption Advisor. Currently, the system detects risks, generates resolution packages with email drafts, and evaluates playbooks — but never actually sends emails. The email-automation feature closes this loop by enabling the system to send alert notifications, escalation emails, and resolution emails to stakeholders based on configurable rules tied to risk events, severity thresholds, and playbook triggers.

## Glossary

- **Email_Service**: The backend service responsible for composing, queuing, and dispatching outbound emails via SMTP
- **Alert_Rule**: A user-defined configuration that maps a risk condition (severity, disruption type, supplier) to an email action (template, recipients, priority)
- **Email_Template**: A reusable email structure with placeholders for dynamic content (supplier name, risk severity, shipment details, recommendations)
- **Notification_Queue**: An ordered list of pending outbound emails awaiting dispatch by the Email_Service
- **Recipient_Group**: A named set of email addresses associated with a role or escalation tier (e.g., "Operations Team", "CFO Office")
- **Cooldown_Period**: A minimum time interval between repeated emails for the same risk event to prevent notification flooding
- **Delivery_Record**: A log entry capturing the outcome of an email send attempt (success, failure, bounce, timestamp)
- **Escalation_Chain**: An ordered sequence of Recipient_Groups contacted progressively when a risk remains unresolved
- **Risk_Engine**: The existing service that classifies disruption severity and produces RiskAssessment objects
- **Playbook_Engine**: The existing service that evaluates risks against automated playbook rules and triggers executions

## Requirements

### Requirement 1: Email Service Configuration

**User Story:** As an administrator, I want to configure SMTP credentials and sender identity for outbound emails, so that the system can send emails through our organization's mail server.

#### Acceptance Criteria

1. THE Email_Service SHALL load SMTP configuration (host, port, username, password, sender address, use_tls flag) from environment variables
2. WHEN the application starts, THE Email_Service SHALL validate SMTP connectivity and log the connection status
3. IF SMTP credentials are missing or invalid, THEN THE Email_Service SHALL log a warning and disable email dispatch without crashing the application
4. THE Email_Service SHALL support both TLS and STARTTLS connection modes

### Requirement 2: Alert Rule Definition

**User Story:** As an operations manager, I want to define rules that trigger email alerts based on risk conditions, so that the right people are notified automatically when disruptions occur.

#### Acceptance Criteria

1. THE Email_Service SHALL support Alert_Rules that specify: severity threshold (low, medium, high, critical), disruption type filter, supplier filter, recipient list, and email template identifier
2. WHEN a new RiskAssessment is produced by the Risk_Engine with severity at or above an Alert_Rule threshold, THE Email_Service SHALL enqueue an email to the configured recipients
3. THE Email_Service SHALL evaluate all active Alert_Rules against each new RiskAssessment
4. WHERE an Alert_Rule specifies a disruption type filter, THE Email_Service SHALL send the email only when the RiskAssessment disruption_type matches the filter
5. WHERE an Alert_Rule specifies a supplier filter, THE Email_Service SHALL send the email only when the RiskAssessment supplier matches the filter

### Requirement 3: Email Template System

**User Story:** As an operations manager, I want email content to be generated from templates with dynamic risk data, so that recipients receive clear, actionable information about each disruption.

#### Acceptance Criteria

1. THE Email_Template system SHALL support placeholders for: supplier_name, severity, disruption_type, summary, recommendations, shipment_id, origin, destination, detected_at, and confidence_score
2. WHEN an email is composed, THE Email_Service SHALL substitute all placeholders in the Email_Template with values from the triggering RiskAssessment
3. THE Email_Template system SHALL provide default templates for: risk_alert, escalation_notice, resolution_update, and daily_digest
4. IF a placeholder value is missing from the RiskAssessment, THEN THE Email_Service SHALL substitute an empty string and log a warning
5. THE Email_Template system SHALL render emails in both plain text and HTML formats

### Requirement 4: Notification Queue and Dispatch

**User Story:** As a system operator, I want emails to be queued and dispatched asynchronously, so that email sending does not block risk analysis or degrade system performance.

#### Acceptance Criteria

1. WHEN an Alert_Rule triggers, THE Email_Service SHALL add the composed email to the Notification_Queue rather than sending synchronously
2. THE Email_Service SHALL process the Notification_Queue using a background worker with a configurable dispatch interval (default: 30 seconds)
3. IF an email dispatch fails, THEN THE Email_Service SHALL retry the dispatch up to 3 times with exponential backoff (30s, 60s, 120s)
4. IF all retry attempts fail, THEN THE Email_Service SHALL mark the Delivery_Record as failed and log the error with the SMTP response
5. WHILE the Notification_Queue contains emails, THE Email_Service SHALL dispatch them in priority order (urgent before normal)

### Requirement 5: Cooldown and Deduplication

**User Story:** As a recipient, I want to avoid being flooded with duplicate notifications for the same risk event, so that I can focus on actionable alerts.

#### Acceptance Criteria

1. THE Email_Service SHALL enforce a configurable Cooldown_Period (default: 1 hour) per unique combination of risk_id and recipient
2. WHEN an Alert_Rule triggers for a risk_id that was already emailed to the same recipient within the Cooldown_Period, THE Email_Service SHALL suppress the duplicate email
3. THE Email_Service SHALL reset the Cooldown_Period for a risk_id when the severity of that risk increases (e.g., medium to critical)
4. THE Email_Service SHALL log all suppressed emails with the reason for suppression

### Requirement 6: Escalation Chain Support

**User Story:** As a supply chain director, I want unresolved critical risks to automatically escalate to senior leadership after a defined time window, so that high-impact disruptions receive executive attention.

#### Acceptance Criteria

1. WHERE an Escalation_Chain is configured for a severity level, THE Email_Service SHALL send the initial alert to the first Recipient_Group in the chain
2. WHEN a risk remains at critical severity for longer than the escalation delay (default: 2 hours), THE Email_Service SHALL send an escalation email to the next Recipient_Group in the chain
3. IF the risk severity is downgraded before the escalation delay expires, THEN THE Email_Service SHALL cancel the pending escalation
4. THE Email_Service SHALL include the elapsed time and any actions taken in escalation emails

### Requirement 7: Resolution Package Email Dispatch

**User Story:** As an operations manager, I want the system to send resolution package emails (carrier, alternate supplier, internal escalation) when a playbook triggers, so that mitigation actions begin immediately without manual intervention.

#### Acceptance Criteria

1. WHEN the Playbook_Engine triggers a resolution action, THE Email_Service SHALL dispatch the carrier email, alternate supplier email, and internal escalation email from the ResolutionPackage
2. THE Email_Service SHALL respect the send_within_hours deadline specified in each ResolutionEmail
3. IF a resolution email fails to send within its deadline, THEN THE Email_Service SHALL log an SLA breach and notify the administrator
4. THE Email_Service SHALL attach the CFOSummary as a formatted section in the internal escalation email

### Requirement 8: Delivery Tracking and Audit Log

**User Story:** As an administrator, I want a complete audit trail of all sent emails, so that I can verify delivery, troubleshoot failures, and demonstrate compliance.

#### Acceptance Criteria

1. THE Email_Service SHALL create a Delivery_Record for every email dispatch attempt containing: timestamp, recipient, subject, template_id, risk_id, status (queued, sent, failed, bounced), and SMTP response code
2. THE Email_Service SHALL expose delivery records through an API endpoint with filtering by status, date range, and recipient
3. WHEN an email is successfully sent, THE Email_Service SHALL update the Delivery_Record status to "sent" with the SMTP message ID
4. THE Email_Service SHALL retain Delivery_Records for a configurable period (default: 90 days)

### Requirement 9: Role-Based Email Permissions

**User Story:** As an administrator, I want email automation rules to respect the existing role-based access control, so that only authorized users can create, modify, or disable alert rules.

#### Acceptance Criteria

1. THE Email_Service SHALL restrict Alert_Rule creation and modification to users with the ADMIN or BUYER role
2. THE Email_Service SHALL allow users with the VIEWER role to view Alert_Rules and Delivery_Records but not modify them
3. WHEN a user without sufficient permissions attempts to modify an Alert_Rule, THE Email_Service SHALL return a 403 Forbidden response
4. THE Email_Service SHALL log all Alert_Rule modifications with the acting user's identity and timestamp

### Requirement 10: Daily Digest Email

**User Story:** As a CFO, I want to receive a daily summary email of all active risks and their statuses, so that I have a consolidated view without needing to check the dashboard.

#### Acceptance Criteria

1. THE Email_Service SHALL generate a daily digest email at a configurable time (default: 08:00 UTC) containing all active risks grouped by severity
2. THE Email_Service SHALL include in the digest: total risk count, new risks since last digest, resolved risks, and top 5 risks by financial exposure
3. WHERE no active risks exist, THE Email_Service SHALL send a brief "all clear" digest confirming no disruptions are detected
4. THE Email_Service SHALL send the daily digest to all members of the configured Recipient_Group for the "daily_digest" template

### Requirement 11: WebSocket Notification on Email Events

**User Story:** As a dashboard user, I want to see real-time notifications when emails are sent or fail, so that I have visibility into the automation system's activity.

#### Acceptance Criteria

1. WHEN an email is successfully dispatched, THE Email_Service SHALL broadcast an "email_sent" event via WebSocket to alert subscribers
2. IF an email dispatch fails after all retries, THEN THE Email_Service SHALL broadcast an "email_failed" event via WebSocket to alert subscribers
3. THE WebSocket event SHALL include: email_id, recipient (masked), subject, risk_id, and status

### Requirement 12: Email Automation Toggle

**User Story:** As an administrator, I want to enable or disable the entire email automation system without restarting the application, so that I can quickly stop all outbound emails during maintenance or incidents.

#### Acceptance Criteria

1. THE Email_Service SHALL support a global enabled/disabled toggle accessible via API endpoint
2. WHILE the Email_Service is disabled, THE Notification_Queue SHALL continue to accumulate emails but the Email_Service SHALL not dispatch them
3. WHEN the Email_Service is re-enabled, THE Email_Service SHALL process all queued emails that have not exceeded their send_within_hours deadline
4. WHEN the Email_Service is re-enabled, THE Email_Service SHALL discard queued emails that have exceeded their send_within_hours deadline and log them as expired
