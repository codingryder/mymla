"""All user-facing copy, bilingual (Malayalam default, English alternate).

Lookup: STRINGS[lang][key]  where lang ∈ {"mal", "eng"}.
Templates with placeholders use Python str.format conventions (e.g. {ward_name}).

Strings are sourced verbatim from BRD v1.0 §3–§7.
"""

from __future__ import annotations


LANGS = ("mal", "eng")
DEFAULT_LANG = "mal"


def t(lang: str | None, key: str, **fmt) -> str:
    """Lookup helper. Falls back to default lang then English on KeyError."""
    lang = lang if lang in LANGS else DEFAULT_LANG
    bundle = STRINGS.get(lang, STRINGS[DEFAULT_LANG])
    value = bundle.get(key) or STRINGS["eng"].get(key) or key
    if fmt:
        try:
            return value.format(**fmt)
        except (KeyError, IndexError):
            return value
    return value


STRINGS: dict[str, dict[str, str]] = {

    # ─── Malayalam (default) ─────────────────────────────────────────────────
    "mal": {
        # Phase 1 — Onboarding
        "welcome_body":
            "നമസ്കാരം! നിങ്ങളുടെ MyMLA വാട്സ്ആപ്പ് ചാറ്റ്ബോട്ടിലേക്ക് സ്വാഗതം.\n"
            "മുന്നോട്ട് പോകുന്നതിനായി ദയവായി നിങ്ങളുടെ ഭാഷ തിരഞ്ഞെടുക്കുക:",
        "welcome_lang_mal": "മലയാളം (Default)",
        "welcome_lang_eng": "English",

        "aadhaar_prompt":
            "നിങ്ങളുടെ 12 അക്ക ആധാർ നമ്പർ രേഖപ്പെടുത്തുക. "
            "(ഇത് നിർബന്ധമല്ല, ഒഴിവാക്കണമെങ്കിൽ താഴെയുള്ള 'ഒഴിവാക്കുക' ബട്ടൺ അമർത്തുക).",
        "aadhaar_skip_button": "⏩ ഒഴിവാക്കുക",
        "aadhaar_validation_error":
            "❌ തെറ്റായ വിവരങ്ങൾ. ദയവായി സാധുവായ ഒരു 12 അക്ക ആധാർ നമ്പർ "
            "രേഖപ്പെടുത്തുക അല്ലെങ്കിൽ 'ഒഴിവാക്കുക' തിരഞ്ഞെടുക്കുക.",
        "aadhaar_saved": "✓ ആധാർ വിവരം സ്വീകരിച്ചു.",

        "ward_prompt":
            "താഴെയുള്ള ബട്ടൺ അമർത്തി നിങ്ങളുടെ *വാർഡ്* തിരഞ്ഞെടുക്കുക (നിർബന്ധം):",
        "ward_list_header": "📍 വാർഡ് തിരഞ്ഞെടുക്കുക",
        "ward_list_button": "വാർഡ് തിരഞ്ഞെടുക്കുക",
        "ward_section_title": "വാർഡുകൾ",

        "booth_prompt":
            "നിങ്ങൾ തിരഞ്ഞെടുത്തിട്ടുള്ള വാർഡിലെ ({ward_name}) നിങ്ങളുടെ *ബൂത്ത് നമ്പർ* "
            "താഴെ നൽകിയിരിക്കുന്ന ലിസ്റ്റിൽ നിന്നും തിരഞ്ഞെടുക്കാം. "
            "(ഇത് നിർബന്ധമല്ല, ഒഴിവാക്കാൻ താഴെയുള്ള ബട്ടൺ അമർത്തുക):",
        "booth_list_header": "📦 ബൂത്ത് തിരഞ്ഞെടുക്കുക",
        "booth_list_button": "ബൂത്ത് തിരഞ്ഞെടുക്കുക",
        "booth_section_title": "ബൂത്ത് നമ്പറുകൾ",
        "booth_skip_button": "⏩ ഒഴിവാക്കുക",
        "booth_next_page": "➡️ അടുത്ത പേജ്",
        "booth_row_title": "ബൂത്ത് {booth}",

        "pin_prompt":
            "ദയവായി നിങ്ങളുടെ 6 അക്ക പിൻകോഡ് (PIN Code) രേഖപ്പെടുത്തുക (നിർബന്ധം):",
        "pin_validation_error":
            "❌ തെറ്റായ പിൻകോഡ്. ദയവായി 6 അക്കങ്ങളുള്ള ശരിയായ പിൻകോഡ് വീണ്ടും ടൈപ്പ് ചെയ്യുക:",
        "onboarding_complete":
            "✅ രജിസ്ട്രേഷൻ പൂർത്തിയായി! പ്രധാന മെനു താഴെ:",

        # Phase 2 — Main Menu
        "menu_header": "പ്രധാന മെനു",
        "menu_body":
            "നിങ്ങൾക്ക് ആവശ്യമുള്ള സേവനം താഴെ നൽകിയിരിക്കുന്നവയിൽ നിന്നും തിരഞ്ഞെടുക്കുക:",
        "menu_button": "സേവനങ്ങൾ",
        "menu_section_title": "MyMLA സേവനങ്ങൾ",
        "menu_opt_complaint":  "📝 പരാതി രജിസ്ട്രേഷൻ",
        "menu_opt_meeting":    "🗓 കൂടിക്കാഴ്ചയ്ക്കുള്ള സമയം ബുക്ക് ചെയ്യുക",
        "menu_opt_location":   "📍 എന്റെ എം.എൽ.എ എവിടെയുണ്ട്?",
        "menu_opt_event":      "✉️ ചടങ്ങുകളിലേക്ക് ക്ഷണിക്കുക",
        "menu_opt_schedule":   "📊 എം.എൽ.എയുടെ പരിപാടികൾ കാണുക",

        # Phase 6 — Complaint
        "complaint_category_body":
            "ദയവായി നിങ്ങളുടെ പരാതി ഏത് വിഭാഗത്തിൽ പെടുന്നതാണെന്ന് തിരഞ്ഞെടുക്കുക:",
        "complaint_category_header": "പരാതി വിഭാഗം",
        "complaint_category_button": "വിഭാഗം",
        "complaint_cat_water":  "🚰 കുടിവെള്ളം",
        "complaint_cat_road":   "🛣 റോഡ്",
        "complaint_cat_house":  "🏠 ഭവനം",
        "complaint_cat_waste":  "🗑 മാലിന്യ സംസ്കരണം",
        "complaint_cat_other":  "📁 മറ്റുള്ളവ",

        "complaint_description_prompt":
            "നിങ്ങളുടെ പരാതിയെക്കുറിച്ചുള്ള വിവരങ്ങൾ താഴെ ടൈപ്പ് ചെയ്യുകയോ "
            "അല്ലെങ്കിൽ ഒരു *വോയിസ് മെസ്സേജ് (Voice Note)* ആയി അയക്കുകയോ ചെയ്യാം:",
        "complaint_voice_received":
            "🎙 വോയിസ് മെസ്സേജ് സ്വീകരിച്ചു — ഇപ്പോൾ പരിശോധിച്ച് ടെക്സ്റ്റാക്കുന്നു...",
        "complaint_voice_transcribed":
            "✓ പരാതി രേഖപ്പെടുത്തി:\n_{transcript}_",
        "complaint_voice_failed":
            "⚠️ വോയിസ് മെസ്സേജ് പരിശോധിക്കാൻ കഴിഞ്ഞില്ല. ദയവായി വീണ്ടും അയക്കുക "
            "അല്ലെങ്കിൽ ടൈപ്പ് ചെയ്യുക.",

        "complaint_image_initial":
            "ഈ പരാതിയുമായി ബന്ധപ്പെട്ട ചിത്രങ്ങൾ ഉണ്ടെങ്കിൽ അയക്കുക (പരമാവധി 5 ചിത്രങ്ങൾ). "
            "ചിത്രങ്ങൾ ഇല്ലെങ്കിലോ, അയച്ചു കഴിഞ്ഞെങ്കിലോ താഴെയുള്ള 'പൂർത്തിയായി' ബട്ടൺ അമർത്തുക:",
        "complaint_image_progress":
            "വിജയകരമായി ചിത്രം ലഭിച്ചു ({count}/5). കൂടുതൽ ചിത്രങ്ങൾ അയക്കാം, "
            "അല്ലെങ്കിൽ താഴെയുള്ള ബട്ടൺ അമർത്തുക:",
        "complaint_image_done_button": "✅ പൂർത്തിയായി",
        "complaint_image_over_cap":
            "⚠️ പരമാവധി 5 ചിത്രങ്ങൾ മാത്രമേ അറ്റാച്ച് ചെയ്യാൻ സാധിക്കൂ. "
            "നിങ്ങളുടെ നിലവിലെ ചിത്രങ്ങൾ രേഖപ്പെടുത്തിയിട്ടുണ്ട്. അടുത്ത ഘട്ടത്തിലേക്ക് നീങ്ങുന്നു.",

        "complaint_leader_ref_prompt":
            "നിങ്ങളുടെ പ്രദേശത്തെ പ്രാദേശിക നേതാവിന്റെ പേരോ ഫോൺ നമ്പറോ അറിയാമെങ്കിൽ "
            "റഫറൻസിനായി ഇവിടെ നൽകാം (ഒഴിവാക്കാൻ താഴെയുള്ള ബട്ടൺ അമർത്തുക):",
        "complaint_leader_skip_button": "⏩ ഒഴിവാക്കുക",

        "complaint_success":
            "🎉 നിങ്ങളുടെ പരാതി വിജയകരമായി രജിസ്റ്റർ ചെയ്തിരിക്കുന്നു!\n\n"
            "🆔 *നിങ്ങളുടെ യുണീക് പരാതി നമ്പർ:* `{ticket_id}`\n\n"
            "ഈ നമ്പർ ഉപയോഗിച്ച് നിങ്ങൾക്ക് തുടർനടപടികൾ പരിശോധിക്കാവുന്നതാണ്. "
            "ഞങ്ങളുടെ ഓഫീസ് ഇത് എത്രയും വേഗം പരിശോധിക്കുന്നതായിരിക്കും. നന്ദി!",

        # Phase 7.1 — Meeting
        "meeting_agenda_body": "നിങ്ങൾ കൂടിക്കാഴ്ച ആവശ്യപ്പെടുന്നത് ഏത് വിഷയത്തിലാണ്?",
        "meeting_agenda_header": "കൂടിക്കാഴ്ച അജണ്ട",
        "meeting_agenda_button": "അജണ്ട",
        "meeting_agenda_dev":     "🏗 വികസന നിർദ്ദേശം",
        "meeting_agenda_welfare": "🤝 ക്ഷേമ സഹായം",
        "meeting_agenda_grievance":"⚠️ പൊതു പരാതി",
        "meeting_summary_prompt":
            "ദയവായി കൂടിക്കാഴ്ചയുടെ ലക്ഷ്യം ഏതാനും വാക്കുകളിൽ ടൈപ്പ് ചെയ്യുക:",
        "meeting_window_prompt":
            "ഏത് ആഴ്ച/മാസമാണ് നിങ്ങൾക്ക് അനുയോജ്യം എന്നു സൂചിപ്പിക്കാമോ? "
            "(ഉദാ: 'ഈ ആഴ്ച', 'അടുത്ത തിങ്കളാഴ്ച', 'ജൂൺ രണ്ടാം ആഴ്ച'):",
        "meeting_success":
            "✅ നിങ്ങളുടെ കൂടിക്കാഴ്ച അഭ്യർത്ഥന രേഖപ്പെടുത്തി!\n"
            "എം.എൽ.എയുടെ ഓഫീസ് മാനേജർ കൂടിക്കാഴ്ച സ്ഥിരീകരണവുമായി "
            "എത്രയും വേഗം ബന്ധപ്പെടുന്നതാണ്. നന്ദി.",

        # Phase 7.2 — Where is my MLA
        "location_card":
            "📍 *എം.എൽ.എയുടെ നിലവിലെ സ്ഥിതി*\n\n"
            "{status}\n\n"
            "_അവസാനം പുതുക്കിയത്: {updated_at}_",
        "location_status_assembly":
            "നിയമസഭാ സമ്മേളനത്തിൽ പങ്കെടുക്കുന്നു (തിരുവനന്തപുരം).",
        "location_status_inspection":
            "{ward_name} വാർഡിൽ പരിശോധനകൾ നടത്തുന്നു.",
        "location_status_office":
            "എം.എൽ.എ ഓഫീസിൽ പൗരന്മാരെ കാണുന്നു.",

        # Phase 7.3 — Event Invitation
        "event_name_prompt": "ദയവായി പരിപാടിയുടെ പേര് / ലക്ഷ്യം ടൈപ്പ് ചെയ്യുക:",
        "event_datetime_prompt":
            "പരിപാടി എപ്പോഴാണ്? (ഉദാ: '15 ജൂൺ 2026, വൈകുന്നേരം 6 മണി'):",
        "event_venue_prompt": "ദയവായി പരിപാടി നടക്കുന്ന സ്ഥലം ടൈപ്പ് ചെയ്യുക:",
        "event_asset_prompt":
            "ദയവായി ക്ഷണപത്രത്തിന്റെ ചിത്രം (PNG) അല്ലെങ്കിൽ PDF അയക്കുക. "
            "(വേണ്ടെങ്കിൽ താഴെയുള്ള ബട്ടൺ അമർത്തുക):",
        "event_asset_skip_button": "⏩ ഒഴിവാക്കുക",
        "event_success":
            "✅ നിങ്ങളുടെ ക്ഷണം എം.എൽ.എയുടെ പബ്ലിക് റിലേഷൻസ് ടീമിന് അയച്ചു. "
            "ഞങ്ങൾ എത്രയും വേഗം പ്രതികരിക്കും. നന്ദി!",

        # Phase 7.4 — Schedule Chart
        "schedule_header": "📊 *എം.എൽ.എയുടെ വരുന്ന 7 ദിവസത്തെ പരിപാടികൾ*\n",
        "schedule_empty": "നിലവിൽ പബ്ലിക് പരിപാടികൾ ഒന്നും ഷെഡ്യൂൾ ചെയ്തിട്ടില്ല.",
        "schedule_row": "• *{date}* — {title}\n  📍 {venue}",

        # Common / fallbacks
        "session_reset_notice":
            "നിങ്ങളുടെ സെഷൻ 30 മിനിറ്റിലേറെ നിശ്ചലമായതിനാൽ പുനഃസജ്ജമാക്കി. "
            "നമുക്ക് വീണ്ടും ആരംഭിക്കാം.",
        "back_to_menu": "🏠 പ്രധാന മെനുവിലേക്ക്",
        "unknown_input":
            "ക്ഷമിക്കണം, അത് മനസ്സിലായില്ല. ദയവായി താഴെയുള്ള ബട്ടണുകൾ ഉപയോഗിക്കുക "
            "അല്ലെങ്കിൽ 'menu' എന്ന് ടൈപ്പ് ചെയ്ത് പ്രധാന മെനുവിലേക്ക് മടങ്ങുക.",
    },

    # ─── English (parallel path) ─────────────────────────────────────────────
    "eng": {
        # Phase 1 — Onboarding
        "welcome_body":
            "Welcome to your MyMLA WhatsApp Chatbot. "
            "Please select your preferred language to proceed:",
        "welcome_lang_mal": "മലയാളം (Malayalam)",
        "welcome_lang_eng": "English",

        "aadhaar_prompt":
            "Please enter your 12-digit Aadhaar Number. "
            "(This is optional. You can skip this step by clicking the 'Skip' button below).",
        "aadhaar_skip_button": "⏩ Skip",
        "aadhaar_validation_error":
            "❌ Invalid format. Please enter a valid 12-digit Aadhaar number or press 'Skip'.",
        "aadhaar_saved": "✓ Aadhaar saved.",

        "ward_prompt":
            "Please click the button below to select your *Ward* (Mandatory):",
        "ward_list_header": "📍 Select Ward",
        "ward_list_button": "Select Ward",
        "ward_section_title": "Wards",

        "booth_prompt":
            "You can now select your *Booth Number* for the selected ward "
            "({ward_name}) from the list below. (This is optional, click the button below to bypass):",
        "booth_list_header": "📦 Select Booth",
        "booth_list_button": "Select Booth",
        "booth_section_title": "Booth Numbers",
        "booth_skip_button": "⏩ Skip",
        "booth_next_page": "➡️ Next page",
        "booth_row_title": "Booth {booth}",

        "pin_prompt":
            "Please enter your 6-digit Postal PIN Code (Mandatory):",
        "pin_validation_error":
            "❌ Invalid PIN Code. Please enter a valid 6-digit numeric PIN code:",
        "onboarding_complete":
            "✅ Registration complete! Main menu below:",

        # Phase 2 — Main Menu
        "menu_header": "Main Menu",
        "menu_body":
            "Please select the service you wish to access from the options below:",
        "menu_button": "Services",
        "menu_section_title": "MyMLA Services",
        "menu_opt_complaint":  "📝 Complaint Registration",
        "menu_opt_meeting":    "🗓 Schedule a Meeting (Appointment)",
        "menu_opt_location":   "📍 Where Is my MLA",
        "menu_opt_event":      "✉️ Invite for an Event",
        "menu_opt_schedule":   "📊 View My Program Chart",

        # Phase 6 — Complaint
        "complaint_category_body":
            "Please select the category that best describes your complaint:",
        "complaint_category_header": "Complaint Category",
        "complaint_category_button": "Category",
        "complaint_cat_water":  "🚰 Drinking Water",
        "complaint_cat_road":   "🛣 Road",
        "complaint_cat_house":  "🏠 House",
        "complaint_cat_waste":  "🗑 Waste Management",
        "complaint_cat_other":  "📁 Other",

        "complaint_description_prompt":
            "Please type your complaint details below, "
            "or send it directly as a *Voice Note*:",
        "complaint_voice_received":
            "🎙 Voice note received — transcribing now...",
        "complaint_voice_transcribed":
            "✓ Recorded your complaint:\n_{transcript}_",
        "complaint_voice_failed":
            "⚠️ Couldn't transcribe the voice note. Please resend or type the details.",

        "complaint_image_initial":
            "Please upload images related to this complaint (Maximum 5 images). "
            "If you have no images or are finished uploading, click 'Done Uploading':",
        "complaint_image_progress":
            "Image successfully attached ({count}/5). You can send more images, "
            "or click the button below to finish:",
        "complaint_image_done_button": "✅ Done Uploading",
        "complaint_image_over_cap":
            "⚠️ You have reached the maximum limit of 5 images. "
            "Proceeding to the next step with the current uploads.",

        "complaint_leader_ref_prompt":
            "If you want to add a reference, please provide your local neighborhood leader's "
            "name or contact number (Click the button below to bypass):",
        "complaint_leader_skip_button": "⏩ Skip",

        "complaint_success":
            "🎉 Your complaint has been successfully registered!\n\n"
            "🆔 *Your Unique Complaint ID:* `{ticket_id}`\n\n"
            "Please save this ticket ID for all your future tracking reference. "
            "Our office will review this shortly. Thank you!",

        # Phase 7.1 — Meeting
        "meeting_agenda_body": "What is the agenda for the meeting you'd like to request?",
        "meeting_agenda_header": "Meeting Agenda",
        "meeting_agenda_button": "Agenda",
        "meeting_agenda_dev":     "🏗 Development Proposal",
        "meeting_agenda_welfare": "🤝 Welfare Support",
        "meeting_agenda_grievance":"⚠️ General Grievance",
        "meeting_summary_prompt":
            "Please type a brief summary of the meeting objective:",
        "meeting_window_prompt":
            "Which week/month would suit you best? "
            "(e.g. 'this week', 'next Monday', 'second week of June'):",
        "meeting_success":
            "✅ Your meeting request has been recorded!\n"
            "The MLA's office manager will coordinate confirmation with you shortly. Thank you.",

        # Phase 7.2 — Where is my MLA
        "location_card":
            "📍 *MLA's Current Status*\n\n"
            "{status}\n\n"
            "_Last updated: {updated_at}_",
        "location_status_assembly":
            "Currently attending the Legislative Assembly Session in Thiruvananthapuram.",
        "location_status_inspection":
            "Conducting active community inspections inside Ward {ward_name}.",
        "location_status_office":
            "Meeting citizens at the MLA's constituency office.",

        # Phase 7.3 — Event Invitation
        "event_name_prompt": "Please type the event name / objective:",
        "event_datetime_prompt":
            "When is the event? (e.g. '15 June 2026, 6 PM'):",
        "event_venue_prompt": "Please type the venue / address:",
        "event_asset_prompt":
            "Please send the invitation card (PNG) or PDF. "
            "(Click the button below to skip):",
        "event_asset_skip_button": "⏩ Skip",
        "event_success":
            "✅ Your invitation has been routed to the MLA's public relations team. "
            "We'll respond shortly. Thank you!",

        # Phase 7.4 — Schedule Chart
        "schedule_header": "📊 *MLA's Program Chart — Upcoming 7 Days*\n",
        "schedule_empty": "No public programs are currently scheduled.",
        "schedule_row": "• *{date}* — {title}\n  📍 {venue}",

        # Common / fallbacks
        "session_reset_notice":
            "Your session has been reset after 30 minutes of inactivity. Let's start again.",
        "back_to_menu": "🏠 Back to main menu",
        "unknown_input":
            "Sorry, I didn't catch that. Please use the buttons below or type 'menu' "
            "to return to the main menu.",
    },
}
