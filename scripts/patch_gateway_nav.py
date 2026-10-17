from pathlib import Path

path = Path(r"F:\ogn_ROOM\.worktrees\gateway-navigation-20261003\templates\base.html")
text = path.read_text(encoding="utf-8")

replacements = {
    '''<a class="brand" href="{% url 'bookings:calendar' %}">''': '''<a class="brand" href="{% url 'bookings:lodging_about' %}">''',
    '''<li><a {% if request.resolver_match.url_name == 'calendar' or request.resolver_match.url_name == 'calendar_root' %}aria-current="page"{% endif %} href="{% url 'bookings:calendar' %}">หน้าแรก</a></li>''': '''<li><a {% if request.resolver_match.url_name == 'lodging_about' %}aria-current="page"{% endif %} href="{% url 'bookings:lodging_about' %}">ศูนย์บริการ</a></li>\n            <li><a {% if request.resolver_match.url_name == 'calendar' or request.resolver_match.url_name == 'calendar_root' %}aria-current="page"{% endif %} href="{% url 'bookings:calendar' %}">สถานะห้อง</a></li>''',
    '''<li><a {% if request.resolver_match.url_name == 'calendar' or request.resolver_match.url_name == 'calendar_root' %}aria-current="page"{% endif %} href="{% url 'bookings:calendar' %}">สถานะห้องวันนี้</a></li>\n            <li><a {% if request.resolver_match.url_name == 'lodging_index' or 'lodging' in request.path %}aria-current="page"{% endif %} href="{% url 'bookings:lodging_index' %}">จองห้องพัก</a></li>\n            <li><a {% if request.resolver_match.url_name == 'about' %}aria-current="page"{% endif %} href="{% url 'bookings:about' %}">รู้จัก SIGROOM</a></li>''': '''<li><a {% if request.resolver_match.url_name == 'lodging_about' %}aria-current="page"{% endif %} href="{% url 'bookings:lodging_about' %}">ศูนย์บริการ</a></li>\n            <li><a {% if request.resolver_match.url_name == 'calendar' or request.resolver_match.url_name == 'calendar_root' %}aria-current="page"{% endif %} href="{% url 'bookings:calendar' %}">สถานะห้องวันนี้</a></li>\n            <li><a {% if request.resolver_match.url_name == 'about' %}aria-current="page"{% endif %} href="{% url 'bookings:about' %}">รู้จัก SIGROOM</a></li>''',
    '''<li><a {% if request.resolver_match.url_name == 'calendar' or request.resolver_match.url_name == 'calendar_root' %}aria-current="page"{% endif %} href="{% url 'bookings:calendar' %}">สถานะห้องวันนี้</a></li>\n                  <li><a {% if request.resolver_match.url_name == 'lodging_index' or 'lodging' in request.path %}aria-current="page"{% endif %} href="{% url 'bookings:lodging_index' %}">จองห้องพัก</a></li>\n                  <li><a {% if request.resolver_match.url_name == 'about' %}aria-current="page"{% endif %} href="{% url 'bookings:about' %}">รู้จัก SIGROOM</a></li>''': '''<li><a {% if request.resolver_match.url_name == 'lodging_about' %}aria-current="page"{% endif %} href="{% url 'bookings:lodging_about' %}">ศูนย์บริการ</a></li>\n                  <li><a {% if request.resolver_match.url_name == 'calendar' or request.resolver_match.url_name == 'calendar_root' %}aria-current="page"{% endif %} href="{% url 'bookings:calendar' %}">สถานะห้องวันนี้</a></li>\n                  <li><a {% if request.resolver_match.url_name == 'about' %}aria-current="page"{% endif %} href="{% url 'bookings:about' %}">รู้จัก SIGROOM</a></li>''',
}

for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f"Expected block not found:\n{old[:120]}")
    text = text.replace(old, new)

path.write_text(text, encoding="utf-8")
print("patched", path)
