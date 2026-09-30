from app.services.telegram_menu_service import telegram_menu_service
from app.services.channel_webhook_service import channel_webhook_service


def test_main_menu_is_bilingual_and_button_first():
    menu = telegram_menu_service.main_menu()
    assert menu["schema"] == "kemet.telegram_menu.v2"
    labels = [row[0]["text"] for row in menu["reply_markup"]["inline_keyboard"]]
    assert "💼 الوظائف | Jobs" in labels
    assert "🛠️ الخدمات | Services" in labels
    assert "📦 أدوات الأعمال | Business Tools" in labels
    assert "🛍️ المنتجات | Products" not in labels
    assert "🌐 اللغة | Language" in labels
    assert menu["execution_authority"] is False


def test_telegram_callback_extracts_message_id_for_in_place_navigation():
    payload = {
        "callback_query": {
            "id": "cq-1",
            "data": "business_tools",
            "from": {"id": 7, "username": "demo"},
            "message": {"message_id": 42, "chat": {"id": 99, "type": "private"}},
        }
    }
    result = channel_webhook_service.extract_telegram(payload)
    assert result["metadata"]["callback_message_id"] == "42"
    assert result["metadata"]["callback_data"] == "business_tools"


def test_language_selection_routes_to_localized_main_menu():
    result = telegram_menu_service.route_callback("lang:ar")
    assert result["action"] == "main_menu"
    assert result["language"] == "ar"
    menu = telegram_menu_service.main_menu(language=result["language"])
    assert menu["language"] == "ar"


def test_business_tools_groups_products_documents_invoices_and_data():
    result = telegram_menu_service.route_callback("business_tools")
    assert result["action"] == "submenu"
    menu = telegram_menu_service.submenu("business_tools")
    labels = [row[0]["text"] for row in menu["reply_markup"]["inline_keyboard"] if row and row[0]]
    assert "🛍️ المنتجات | Products" in labels
    assert "📄 المستندات | Documents" in labels
    assert "🧾 الفواتير | Invoices" in labels
    assert "📊 البيانات | Data Tools" in labels
    assert "↩️ رجوع | Back" in labels


def test_more_is_secondary_features_only():
    menu = telegram_menu_service.submenu("more")
    labels = [row[0]["text"] for row in menu["reply_markup"]["inline_keyboard"] if row and row[0]]
    assert "📞 الدعم | Support" in labels
    assert "⚙️ الأتمتة | Automation" in labels
    assert "🛍️ المنتجات | Products" not in labels
    assert "📄 المستندات | Documents" not in labels
    assert "🧾 الفواتير | Invoices" not in labels
    assert "📊 البيانات | Data Tools" not in labels


def test_nested_navigation_has_back_and_home_path():
    result = telegram_menu_service.route_callback("jobs")
    assert result["action"] == "submenu"
    menu = telegram_menu_service.submenu("jobs")
    labels = [row[0]["text"] for row in menu["reply_markup"]["inline_keyboard"]
              if row and row[0]]
    assert "↩️ رجوع | Back" in labels


def test_orders_deliveries_is_a_supported_non_executing_action():
    result = telegram_menu_service.route_callback("orders_deliveries")
    assert result["action"] == "orders_deliveries"
    assert result["execution"] is False
    assert result["approval_required"] is True
    menu = telegram_menu_service.submenu("orders")
    labels = [row[0]["text"] for row in menu["reply_markup"]["inline_keyboard"] if row and row[0]]
    assert "📦 التسليمات | Deliveries" in labels


def test_supported_actions_are_non_executing():
    result = telegram_menu_service.route_callback("document_upload")
    assert result["action"] == "document_upload"
    assert result["execution"] is False
    assert result["approval_required"] is True


def test_unknown_callback_fails_closed():
    try:
        telegram_menu_service.route_callback("not-a-real-action")
    except ValueError as exc:
        assert str(exc) == "unknown_callback"
    else:
        raise AssertionError("unknown callback must fail closed")
