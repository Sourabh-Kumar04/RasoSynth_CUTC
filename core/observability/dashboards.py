"""
Dashboards, Alerts & Incident Management

Grafana/Prometheus integration, real-time metrics streaming,
alert rules, and incident response.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    """Notification channels."""
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    EMAIL = "email"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"


@dataclass
class AlertRule:
    """Alert rule definition."""
    rule_id: str
    name: str
    severity: AlertSeverity
    condition: str  # e.g., "gpu_utilization > 95"
    threshold: float
    evaluation_interval: int = 60  # seconds
    notification_channels: List[NotificationChannel] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_triggered: Optional[datetime] = None

    def evaluate(self, metrics: Dict[str, float]) -> bool:
        """Evaluate if rule should trigger."""
        if not self.enabled:
            return False

        value = metrics.get(self.condition.split(" ")[0], 0)
        op = self.condition.split(" ")[1] if len(self.condition.split(" ")) > 1 else ">"

        if op == ">":
            return value > self.threshold
        elif op == ">=":
            return value >= self.threshold
        elif op == "<":
            return value < self.threshold
        elif op == "<=":
            return value <= self.threshold
        elif op == "==":
            return value == self.threshold

        return False


@dataclass
class Alert:
    """Alert instance."""
    alert_id: str
    rule_id: str
    name: str
    severity: AlertSeverity
    message: str
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Incident:
    """Incident record."""
    incident_id: str
    title: str
    severity: AlertSeverity
    status: str = "open"
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    alerts: List[str] = field(default_factory=list)  # Alert IDs
    affected_components: List[str] = field(default_factory=list)
    resolution: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertManager:
    """Manages alerting rules and notifications."""

    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: List[Alert] = []
        self._active_alerts: Dict[str, Alert] = {}
        self._notification_handlers: Dict[NotificationChannel, List[Callable]] = {}
        self._max_alerts = 10000

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self._rules[rule.rule_id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an alert rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get alert rule."""
        return self._rules.get(rule_id)

    async def evaluate_rules(self, metrics: Dict[str, float]) -> List[Alert]:
        """Evaluate all rules against metrics."""
        triggered = []

        for rule in self._rules.values():
            if rule.evaluate(metrics):
                alert = self._trigger_alert(rule, metrics)
                triggered.append(alert)

        return triggered

    def _trigger_alert(
        self,
        rule: AlertRule,
        metrics: Dict[str, float]
    ) -> Alert:
        """Trigger an alert."""
        alert = Alert(
            alert_id=f"alert_{len(self._alerts)}",
            rule_id=rule.rule_id,
            name=rule.name,
            severity=rule.severity,
            message=f"Alert triggered: {rule.name} (threshold: {rule.threshold})",
            triggered_at=datetime.utcnow(),
            metadata={"metrics": metrics}
        )

        self._alerts.append(alert)
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]

        self._active_alerts[alert.alert_id] = alert
        rule.last_triggered = datetime.utcnow()

        return alert

    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        if alert_id in self._active_alerts:
            alert = self._active_alerts[alert_id]
            alert.resolved_at = datetime.utcnow()
            del self._active_alerts[alert_id]
            return True
        return False

    def add_notification_handler(
        self,
        channel: NotificationChannel,
        handler: Callable
    ) -> None:
        """Add notification handler."""
        if channel not in self._notification_handlers:
            self._notification_handlers[channel] = []
        self._notification_handlers[channel].append(handler)

    async def notify(
        self,
        alert: Alert,
        channel: NotificationChannel
    ) -> None:
        """Send alert notification."""
        handlers = self._notification_handlers.get(channel, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception:
                pass

    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """Get active alerts."""
        alerts = list(self._active_alerts.values())
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return alerts

    def get_alert_history(
        self,
        limit: int = 100,
        severity: Optional[AlertSeverity] = None
    ) -> List[Alert]:
        """Get alert history."""
        alerts = self._alerts[-limit:]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return alerts


class IncidentTracker:
    """Tracks and manages incidents."""

    def __init__(self, alert_manager: AlertManager):
        self.alert_manager = alert_manager
        self._incidents: Dict[str, Incident] = {}
        self._incident_alerts: Dict[str, List[str]] = {}

    def create_incident(
        self,
        title: str,
        severity: AlertSeverity,
        alert_ids: Optional[List[str]] = None
    ) -> Incident:
        """Create a new incident."""
        incident_id = f"incident_{len(self._incidents)}"

        incident = Incident(
            incident_id=incident_id,
            title=title,
            severity=severity,
            alerts=alert_ids or []
        )

        self._incidents[incident_id] = incident
        self._incident_alerts[incident_id] = alert_ids or []

        return incident

    def link_alert(self, incident_id: str, alert_id: str) -> bool:
        """Link an alert to an incident."""
        if incident_id in self._incidents:
            self._incidents[incident_id].alerts.append(alert_id)
            if incident_id not in self._incident_alerts:
                self._incident_alerts[incident_id] = []
            self._incident_alerts[incident_id].append(alert_id)
            return True
        return False

    def resolve_incident(
        self,
        incident_id: str,
        resolution: str
    ) -> bool:
        """Resolve an incident."""
        if incident_id in self._incidents:
            incident = self._incidents[incident_id]
            incident.status = "resolved"
            incident.resolved_at = datetime.utcnow()
            incident.resolution = resolution

            # Resolve linked alerts
            for alert_id in incident.alerts:
                asyncio.create_task(self.alert_manager.resolve_alert(alert_id))

            return True
        return False

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get incident by ID."""
        return self._incidents.get(incident_id)

    def get_open_incidents(
        self,
        severity: Optional[AlertSeverity] = None
    ) -> List[Incident]:
        """Get open incidents."""
        incidents = [i for i in self._incidents.values() if i.status == "open"]
        if severity:
            incidents = [i for i in incidents if i.severity == severity]
        return incidents


class PrometheusMetricsServer:
    """Prometheus metrics HTTP server."""

    def __init__(self, port: int = 9090):
        self.port = port
        self._collector = None

    def set_collector(self, collector) -> None:
        """Set metrics collector."""
        self._collector = collector

    async def get_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        if self._collector:
            return self._collector.to_prometheus_format()
        return ""

    async def get_metrics_json(self) -> Dict:
        """Get metrics as JSON."""
        if self._collector:
            return self._collector.get_all_metrics()
        return {}


class GrafanaExporter:
    """Exports metrics for Grafana."""

    def __init__(self):
        self._dashboards: Dict[str, Dict] = {}
        self._panels: List[Dict] = []

    def create_dashboard(
        self,
        name: str,
        panels: List[Dict]
    ) -> str:
        """Create a Grafana dashboard."""
        dashboard_id = f"dash_{len(self._dashboards)}"

        self._dashboards[dashboard_id] = {
            "id": dashboard_id,
            "name": name,
            "panels": panels,
            "created_at": datetime.utcnow().isoformat()
        }

        return dashboard_id

    def add_panel(
        self,
        dashboard_id: str,
        panel: Dict
    ) -> bool:
        """Add a panel to dashboard."""
        if dashboard_id in self._dashboards:
            self._dashboards[dashboard_id]["panels"].append(panel)
            return True
        return False

    def to_grafana_json(self, dashboard_id: str) -> Optional[Dict]:
        """Export dashboard in Grafana JSON format."""
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return None

        return {
            "dashboard": {
                "title": dashboard["name"],
                "panels": dashboard["panels"],
                "timezone": "browser",
                "refresh": "30s"
            },
            "meta": {
                "created": dashboard["created_at"]
            }
        }


class RealTimeMetricsStream:
    """Real-time metrics streaming."""

    def __init__(self):
        self._subscribers: Dict[str, Callable] = {}
        self._buffer: List[Dict] = []
        self._max_buffer = 1000

    async def publish(self, metrics: Dict) -> None:
        """Publish metrics to stream."""
        self._buffer.append({
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        })

        if len(self._buffer) > self._max_buffer:
            self._buffer = self._buffer[-self._max_buffer:]

        # Notify subscribers
        for subscriber_id, handler in self._subscribers.items():
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(metrics)
                else:
                    handler(metrics)
            except Exception:
                pass

    def subscribe(self, subscriber_id: str, handler: Callable) -> None:
        """Subscribe to metrics stream."""
        self._subscribers[subscriber_id] = handler

    def unsubscribe(self, subscriber_id: str) -> bool:
        """Unsubscribe from stream."""
        if subscriber_id in self._subscribers:
            del self._subscribers[subscriber_id]
            return True
        return False

    def get_recent(self, limit: int = 100) -> List[Dict]:
        """Get recent metrics."""
        return self._buffer[-limit:]


class DashboardManager:
    """Manages observability dashboards."""

    def __init__(self):
        self._dashboards: Dict[str, Dict] = {}
        self._metrics_stream = RealTimeMetricsStream()

    def create_dashboard(
        self,
        name: str,
        widgets: List[Dict]
    ) -> str:
        """Create a dashboard."""
        dashboard_id = f"dashboard_{len(self._dashboards)}"

        self._dashboards[dashboard_id] = {
            "id": dashboard_id,
            "name": name,
            "widgets": widgets,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        return dashboard_id

    def get_dashboard(self, dashboard_id: str) -> Optional[Dict]:
        """Get dashboard by ID."""
        return self._dashboards.get(dashboard_id)

    def update_dashboard(
        self,
        dashboard_id: str,
        widgets: List[Dict]
    ) -> bool:
        """Update dashboard widgets."""
        if dashboard_id in self._dashboards:
            self._dashboards[dashboard_id]["widgets"] = widgets
            self._dashboards[dashboard_id]["updated_at"] = datetime.utcnow()
            return True
        return False

    def list_dashboards(self) -> List[Dict]:
        """List all dashboards."""
        return [
            {
                "id": d["id"],
                "name": d["name"],
                "widget_count": len(d["widgets"]),
                "updated_at": d["updated_at"].isoformat()
            }
            for d in self._dashboards.values()
        ]

    def add_widget(
        self,
        dashboard_id: str,
        widget: Dict
    ) -> bool:
        """Add widget to dashboard."""
        if dashboard_id in self._dashboards:
            self._dashboards[dashboard_id]["widgets"].append(widget)
            self._dashboards[dashboard_id]["updated_at"] = datetime.utcnow()
            return True
        return False