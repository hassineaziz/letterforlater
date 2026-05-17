import re

with open('website/templates/base.html', 'r') as f:
    content = f.read()

# 1. Replace Tailwind config and Fonts in head
head_replacement = """
    <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Serif:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet"/>
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
    <title>{% block title %}Heirloom – Delivered When It Matters{% endblock %}</title>
    <script id="tailwind-config">
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    "colors": {
                        "primary": "#9333EA",
                        "primary-container": "#7E22CE",
                        "on-primary": "#ffffff",
                        "secondary": "#7c3aed",
                        "surface": "#f9f9ff",
                        "on-surface": "#141b2b",
                        "surface-variant": "#f3e8ff",
                        "on-surface-variant": "#4d4354",
                        "surface-container-lowest": "#ffffff",
                        "surface-container-low": "#faf5ff",
                        "surface-container": "#f3e8ff",
                        "surface-container-high": "#ede9fe",
                        "surface-container-highest": "#e9d5ff",
                        "outline": "#a78bfa",
                        "outline-variant": "#ddd6fe"
                    },
                    "borderRadius": {
                        "DEFAULT": "0.5rem",
                        "lg": "0.5rem",
                        "xl": "0.75rem",
                        "2xl": "1rem",
                        "3xl": "1.5rem",
                        "full": "9999px"
                    },
                    "fontFamily": {
                        "headline": ["Noto Serif", "serif"],
                        "body": ["Inter", "sans-serif"],
                        "label": ["Inter", "sans-serif"]
                    }
                },
            },
        }
    </script>
"""

content = re.sub(
    r'<!-- Google Fonts: non-blocking load with noscript fallback -->.*?</script>',
    head_replacement.strip(),
    content,
    flags=re.DOTALL
)

# Also need to make sure the style block with linear-gradient body is removed or changed
# Let's just remove the body background style.
content = re.sub(
    r'<style>\s*body \{\s*background: linear-gradient.*?min-height: 100vh;\s*\}',
    '<style>\n        .material-symbols-outlined {\n            font-variation-settings: \'FILL\' 0, \'wght\' 400, \'GRAD\' 0, \'opsz\' 24;\n        }',
    content,
    flags=re.DOTALL
)

# And update the body class
content = content.replace(
    '<body class="font-sans text-gray-800 leading-relaxed"',
    '<body class="bg-surface text-on-surface font-body selection:bg-primary/20 selection:text-primary relative leading-relaxed"'
)

# 2. Replace the navbar
navbar_replacement = """
    <!-- Navigation -->
    <nav class="sticky top-0 w-full z-50 bg-white/90 backdrop-blur-xl border-b border-surface-container-highest mb-4 sm:mb-6 lg:mb-8">
        <div class="flex justify-between items-center h-14 px-4 sm:px-8 max-w-screen-2xl mx-auto w-full">
            <!-- Brand -->
            <a href="/" class="font-headline italic text-2xl text-slate-900">Heirloom</a>

            <!-- Desktop navigation -->
            <div class="hidden md:flex items-center gap-6 lg:gap-10">
                {% if user.is_authenticated %}
                    <a href="{{ url_for('views.add_letter') }}" class="text-slate-600 font-medium uppercase tracking-widest text-[10px] hover:text-primary transition-all duration-300">Write</a>
                    <a href="{{ url_for('views.view_letters', user_id=user.id) }}" class="text-slate-600 font-medium uppercase tracking-widest text-[10px] hover:text-primary transition-all duration-300">My Letters</a>
                    {% if has_received_letters(user) %}
                        <a href="{{ url_for('views.received_letters') }}" class="text-slate-600 font-medium uppercase tracking-widest text-[10px] hover:text-primary transition-all duration-300">Received</a>
                    {% endif %}
                    
                    <!-- Contacts dropdown -->
                    <div class="relative">
                        <button id="contactsDropdown" class="text-slate-600 font-medium uppercase tracking-widest text-[10px] hover:text-primary transition-all duration-300 flex items-center" onclick="toggleContactsDropdown(event)">
                            Contacts
                            <svg class="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                        </button>
                        <div id="contacts-dropdown-menu" class="absolute left-0 top-full mt-2 w-48 sm:w-56 bg-white rounded-xl shadow-lg border border-gray-200 z-[9999] hidden">
                            {% if is_premium_user %}
                            <a href="{{ url_for('views.trusted_contacts') }}" class="block px-3 sm:px-4 py-2 text-xs sm:text-sm text-gray-700 hover:bg-gray-50">Trusted Contacts</a>
                            {% if check_trusted_contact_status(user) %}
                            <a href="{{ url_for('views.verify_death') }}" class="block px-3 sm:px-4 py-2 text-xs sm:text-sm text-gray-700 hover:bg-gray-50">Verify Death</a>
                            {% endif %}
                            {% else %}
                            <a href="{{ url_for('pricing.pricing_page') }}" class="block px-3 sm:px-4 py-2 text-xs sm:text-sm text-blue-600 hover:bg-blue-50 font-semibold">Trusted Contacts (Premium)</a>
                            {% endif %}
                        </div>
                    </div>
                {% else %}
                    <a class="text-slate-600 font-medium uppercase tracking-widest text-[10px] hover:text-primary transition-all duration-300" href="{{ url_for('pricing.pricing_page') }}">Pricing</a>
                    <a class="text-slate-600 font-medium uppercase tracking-widest text-[10px] hover:text-primary transition-all duration-300" href="{{ url_for('views.blog_index') }}">Blog</a>
                {% endif %}
            </div>

            <div class="flex items-center gap-4">
                {% if user.is_authenticated %}
                    <!-- Notification Bell -->
                    <div class="relative flex items-center justify-center pt-1">
                        <button id="notificationDropdown" class="relative p-1 text-slate-600 hover:text-primary focus:outline-none transition-colors">
                            <span class="material-symbols-outlined text-xl">notifications</span>
                            <span id="notification-badge" class="absolute top-0 right-0 bg-primary text-white text-[8px] font-bold rounded-full h-3 w-3 flex items-center justify-center hidden"></span>
                        </button>
                        <!-- Notification Dropdown Menu -->
                        <div id="notification-dropdown-menu" class="absolute right-0 top-full mt-2 w-80 sm:w-96 bg-white rounded-xl shadow-lg border border-gray-200 z-[9999] hidden text-left">
                            <div class="p-3 sm:p-4 border-b border-gray-100">
                                <h3 class="text-base font-semibold text-gray-900">Notifications</h3>
                                <p class="text-xs text-gray-500" id="notification-count">0 unread</p>
                            </div>
                            <div id="notification-list" class="max-h-80 sm:max-h-96 overflow-y-auto">
                                <div id="no-notifications" class="p-8 text-center text-gray-500">
                                    <p class="text-sm">No notifications yet</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Account Dropdown -->
                    <div class="relative hidden md:block">
                        <button id="accountDropdown" class="bg-surface-container-highest hover:bg-outline-variant text-on-surface px-5 py-1.5 rounded-full font-label text-xs font-semibold transition-transform flex items-center" onclick="toggleAccountDropdown(event)">
                            Account
                            <svg class="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                        </button>
                        <div id="account-dropdown-menu" class="absolute right-0 top-full mt-2 w-48 sm:w-56 bg-white rounded-xl shadow-lg border border-gray-200 z-[9999] hidden">
                            <a href="{{ url_for('views.blog_index') }}" class="block px-3 py-2 text-xs text-gray-700 hover:bg-gray-50">Blog</a>
                            <a href="{{ url_for('views.settings') }}" class="block px-3 py-2 text-xs text-gray-700 hover:bg-gray-50">Settings</a>
                            <div class="border-t border-gray-100 my-1"></div>
                            <a href="/logout" class="block px-3 py-2 text-xs text-red-600 hover:bg-red-50">Logout</a>
                        </div>
                    </div>
                {% else %}
                    <a href="/login" class="hidden lg:block text-slate-600 font-medium uppercase tracking-widest text-[10px] hover:text-primary transition-all">Login</a>
                    <a href="/sign-up" class="bg-primary hover:bg-primary-container text-on-primary px-5 py-1.5 rounded-full font-label text-xs font-semibold transition-transform">Start Writing</a>
                {% endif %}

                <!-- Mobile menu button -->
                <button type="button" class="md:hidden text-slate-600 hover:text-primary focus:outline-none p-1" onclick="toggleMobileMenu()" aria-label="Open menu">
                    <span class="material-symbols-outlined text-2xl">menu</span>
                </button>
            </div>
        </div>

        <!-- Mobile menu -->
        <div id="mobile-menu" class="md:hidden hidden bg-white border-t border-surface-container-highest shadow-xl">
            <div class="px-4 py-3 space-y-2">
                {% if user.is_authenticated %}
                    <a href="/" class="block text-sm font-medium text-slate-700 hover:text-primary">Home</a>
                    <a href="{{ url_for('views.add_letter') }}" class="block text-sm font-medium text-slate-700 hover:text-primary">Create Letter</a>
                    <a href="{{ url_for('views.view_letters', user_id=user.id) }}" class="block text-sm font-medium text-slate-700 hover:text-primary">My Letters</a>
                    {% if has_received_letters(user) %}
                        <a href="{{ url_for('views.received_letters') }}" class="block text-sm font-medium text-slate-700 hover:text-primary">Received Letters</a>
                    {% endif %}
                    <a href="{{ url_for('views.settings') }}" class="block text-sm font-medium text-slate-700 hover:text-primary">Settings</a>
                    <a href="/logout" class="block text-sm font-medium text-red-600 hover:text-red-700 mt-2 border-t pt-2 border-surface-container-highest">Logout</a>
                {% else %}
                    <a href="/login" class="block text-sm font-medium text-slate-700 hover:text-primary">Login</a>
                    <a href="/sign-up" class="block text-sm font-medium text-slate-700 hover:text-primary">Sign Up</a>
                    <a href="{{ url_for('pricing.pricing_page') }}" class="block text-sm font-medium text-slate-700 hover:text-primary">Pricing</a>
                {% endif %}
            </div>
        </div>
    </nav>
"""

content = re.sub(r'<!-- Navigation -->.*?</nav>', navbar_replacement.strip(), content, flags=re.DOTALL)

# 3. Replace the footer
footer_replacement = """
    <!-- Footer -->
    <footer class="w-full py-12 px-8 bg-slate-50 border-t border-slate-200 mt-16">
        <div class="flex flex-col md:flex-row justify-between items-center max-w-7xl mx-auto">
            <div class="mb-6 md:mb-0 text-center md:text-left">
                <a href="/" class="font-headline italic text-2xl text-slate-800 mb-2 block">Heirloom</a>
                <p class="font-sans text-[10px] uppercase tracking-[0.2em] text-slate-400">© <span id="currentYear"></span> Heirloom Digital Preservation.</p>
            </div>
            <div class="flex flex-wrap justify-center gap-8">
                <a class="font-sans text-[10px] uppercase tracking-[0.2em] text-slate-400 hover:text-primary transition-colors font-bold" href="#">Security</a>
                <a class="font-sans text-[10px] uppercase tracking-[0.2em] text-slate-400 hover:text-primary transition-colors font-bold" href="{{ url_for('views.privacy_policy') }}">Privacy</a>
                <a class="font-sans text-[10px] uppercase tracking-[0.2em] text-slate-400 hover:text-primary transition-colors font-bold" href="{{ url_for('views.terms_of_service') }}">Terms</a>
                <a class="font-sans text-[10px] uppercase tracking-[0.2em] text-slate-400 hover:text-primary transition-colors font-bold" href="{{ url_for('pricing.pricing_page') }}">Pricing</a>
                <a class="font-sans text-[10px] uppercase tracking-[0.2em] text-slate-400 hover:text-primary transition-colors font-bold" href="{{ url_for('views.blog_index') }}">Blog</a>
            </div>
        </div>
    </footer>
"""

content = re.sub(r'<!-- Footer -->.*?</footer>', footer_replacement.strip(), content, flags=re.DOTALL)


with open('website/templates/base.html', 'w') as f:
    f.write(content)

print("Applied replacements to base.html")
