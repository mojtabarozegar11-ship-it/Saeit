class MojPropRequest(T):
    """Public Moj Prop request intake; no payment or automated advice is created."""
    ROUTE_CHOICES = (
        ("blueprint", "Prop-program design"),
        ("signals", "Educational signals and market brief"),
        ("brief", "Private market brief"),
        ("audit", "mojtaba.bot.ai commercial-gate audit"),
    )
    HORIZON_CHOICES = (
        ("urgent", "Today / urgent"),
        ("week", "This week"),
        ("month", "This month"),
        ("review", "Initial review only"),
    )
    STATUS_CHOICES = (
        ("new", "New"),
        ("reviewing", "Reviewing"),
        ("offer_sent", "Written offer sent"),
        ("approved", "Approved"),
        ("delivered", "Delivered"),
        ("closed", "Closed"),
        ("spam", "Spam / rejected"),
    )
    request_id = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    route = models.CharField(max_length=30, choices=ROUTE_CHOICES)
    horizon = models.CharField(max_length=20, choices=HORIZON_CHOICES)
    notes = models.TextField()
    consent = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    source = models.CharField(max_length=80, default="moj-prop")
    ip_hash = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=300, blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    internal_note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "created_at"), name="mojprop_status_created_idx"),
            models.Index(fields=("email", "created_at"), name="mojprop_email_created_idx"),
            models.Index(fields=("ip_hash", "created_at"), name="mojprop_ip_created_idx"),
        ]
