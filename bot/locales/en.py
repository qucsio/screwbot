TEXTS = {
    "choose_lang": "🌐 Choose your language / Выберите язык:",
    "lang_set": "Language set: English 🇬🇧",
    "choose_role": "Who are you on the SCREW PROD platform?",
    "role_client": "🎧 Client",
    "role_creator": "🎨 Creator",
    "ask_nickname": "Enter your nickname in the system:",
    "no_username": (
        "⚠️ You have no @username set in Telegram. "
        "It's required for contact. Set it in settings and press /start again."
    ),
    "client_registered": (
        "✅ Done, {nickname}! You are registered as a client.\n"
        "Opening the services menu."
    ),
    "creator_ask_service": "What service do you provide? (e.g. 'Producer / beats')",
    "creator_ask_experience": "Tell us about your experience (briefly):",
    "creator_ask_portfolio": "Send your portfolio / social links in one message:",
    "creator_application_sent": (
        "✅ Application sent for moderation. "
        "The admin will contact you in direct messages."
    ),
    "creator_already_pending": "⏳ Your application is already under review.",
    "main_menu": "🎛 SCREW PROD services menu:",
    "menu_ready_beats": "🎧 Ready arrangements & beats",
    "menu_custom_beats": "🎶 Custom arrangements & beats",
    "menu_mixing": "🎚️ Mixing",
    "menu_ghostwriting": "✍️ Lyrics (ghostwriter)",
    "menu_visual": "🖼️ Visuals",
    "menu_videographer": "🎥 Videographer",
    "menu_editing": "🎬 Video editing",
    "menu_photo": "📸 Photoshoot (Moscow)",
    "menu_reviews": "💬 Reviews",
    "menu_my_profile": "👤 My profile",
    "back": "⬅️ Back",
    "wip": "🚧 Section under construction.",
    "mod_new_creator": (
        "🆕 <b>Creator application</b>\n\n"
        "Contact: {contact}\n"
        "Nickname: {nickname}\n"
        "Service: {service}\n"
        "Experience: {experience}\n"
        "Portfolio: {portfolio}"
    ),
    "mod_approve": "✅ Approve",
    "mod_reject": "❌ Reject",
    "mod_approved_admin": "Creator approved.",
    "mod_rejected_admin": "Application rejected.",
    "creator_approved_notify": "🎉 Your application is approved! Welcome to the SCREW PROD team.",
    "creator_rejected_notify": "Unfortunately, your application was rejected.",
    "addbeat_only_creator": "⛔ Only approved creators can add beats.",
    "addbeat_title": "🎵 Beat title:",
    "addbeat_genre": "Genre:",
    "addbeat_key": "Key (e.g. Am, C#):",
    "addbeat_bpm": "BPM (number):",
    "addbeat_bpm_invalid": "Enter BPM as a number (e.g. 140).",
    "addbeat_cover": "Send the cover (photo):",
    "addbeat_cover_invalid": "A photo is required. Send the cover as an image.",
    "addbeat_audio": "Send the audio snippet (audio/file):",
    "addbeat_audio_invalid": "An audio file is required.",
    "addbeat_price_rent": "💸 Rent price (RUB):",
    "addbeat_price_buy": "💰 Buyout price (RUB):",
    "addbeat_price_invalid": "Enter the price as a number.",
    "addbeat_sent": "✅ Beat sent for moderation.",
    "mod_new_beat": (
        "🆕 <b>New beat for moderation</b>\n\n"
        "Author: {author}\n"
        "Title: {title}\n"
        "Genre: {genre} | Key: {key} | BPM: {bpm}\n"
        "Rent: {rent} ₽ | Buyout: {buy} ₽"
    ),
    "beat_approved_notify": "✅ Your beat '{title}' is approved and added to the catalog.",
    "beat_rejected_notify": "❌ Your beat '{title}' was rejected by moderation.",
    "catalog_empty": "😔 No approved beats in the catalog yet.",
    "filter_intro": "🔎 Set up a filter or browse everything:",
    "filter_all": "▶️ Browse all",
    "filter_setup": "🎚 Set up filter",
    "filter_genre": "Choose a genre:",
    "filter_any": "Any",
    "filter_key": "Key (as text) or '-' to skip:",
    "filter_bpm": "BPM range as '120-140' or '-' to skip:",
    "filter_no_results": "😔 Nothing matched your filter.",
    "beat_card": (
        "🎵 <b>{title}</b>\n"
        "Author: {author}\n"
        "Genre: {genre} | Key: {key} | BPM: {bpm}\n"
        "💸 Rent: {rent} ₽ | 💰 Buyout: {buy} ₽\n"
        "({pos}/{total})"
    ),
    "beat_prev": "⬅️",
    "beat_next": "➡️",
    "beat_listen": "▶️ Listen",
    "beat_buy": "💸 Buy",
    "beat_ask": "💬 Ask a question",
    "beat_ask_prompt": "✍️ Write your question about '{title}' — it will go to the admin:",
    "beat_ask_sent": "✅ Question sent.",
    "beat_buy_sent": "✅ Purchase request sent to the admin, he will contact you.",
    "mod_beat_question": (
        "💬 <b>Question about beat</b> '{title}' (id{work_id})\n"
        "From: {contact}\n\n{text}"
    ),
    "mod_beat_buy": (
        "🛒 <b>Purchase request</b> for beat '{title}' (id{work_id})\n"
        "Client: {contact}\nAuthor: {author}\n"
        "Rent: {rent} ₽ | Buyout: {buy} ₽"
    ),
    "order_only_client": "⛔ Only clients can place orders.",
    "order_form_start": "📝 Order brief '{title}'. Answer one message at a time.\n/cancel — abort.",
    "order_form_cancelled": "❌ Order creation cancelled.",
    "order_published": "✅ Your order #{order_id} is published. Waiting for a creator to take it.",
    "order_category_unavailable": "⚠️ Category temporarily unavailable (topic not configured). Try later.",
    "tender_card": "🆕 <b>New order</b> · {title} · #{order_id}\nFrom: {contact}\n\n{body}",
    "btn_take_order": "✅ Take order",
    "order_taken_ok": "You took order #{order_id}. Waiting for client confirmation.",
    "order_already_taken": "The order was already taken by another creator.",
    "order_take_only_creator": "Only approved creators can take orders.",
    "tender_taken_mark": "\n\n🔒 Taken by {contact}",
    "client_creator_took": (
        "🙌 Creator {contact} took your order #{order_id}.\n"
        "Approve them and proceed to payment?"
    ),
    "btn_confirm_creator": "✅ Approve",
    "btn_cancel_order": "❌ Cancel order",
    "client_pay_instructions": (
        "💳 Order #{order_id} confirmed.\n\n"
        "Pay <b>50% prepayment</b> to:\n{details}\n\n"
        "After payment the admin confirms it and you get the creator's contact."
    ),
    "admin_await_prepay": (
        "💰 <b>Order #{order_id}</b> ({title})\n"
        "Client: {client} · Creator: {creator}\n"
        "Client approved the creator. Awaiting 50% prepayment."
    ),
    "btn_confirm_prepay": "✅ Confirm prepayment",
    "btn_confirm_final": "✅ Confirm final payment",
    "contacts_to_creator": "🤝 Prepayment for order #{order_id} received!\nClient contact: {contact}\nGet in touch and start.",
    "contacts_to_client": "🤝 Prepayment received!\nCreator contact: {contact}\nThey will reach out.",
    "admin_prepay_done": "Prepayment marked, contacts sent.",
    "admin_enter_payout": "Enter the payout amount for the creator on order #{order_id} (number):",
    "admin_payout_invalid": "Enter the amount as a number.",
    "admin_final_done": "Order #{order_id} closed, credited {amount} ₽.",
    "creator_balance_credited": "💵 For order #{order_id} you were credited {amount} ₽ (available for payout).",
    "client_order_completed": "🎉 Order #{order_id} completed. Thank you!",
    "order_cancelled_client": "Order #{order_id} cancelled.",
    "admin_order_cancelled": "⚠️ Client cancelled order #{order_id}. Returned to moderation.",
    "menu_my_orders": "📁 My orders",
    "hub_orders_client": "📁 Your orders:",
    "hub_orders_creator": "📁 Your orders in progress:",
    "hub_orders_empty": "You have no active orders yet.",
    "order_card_header": "📦 <b>Order #{order_id}</b> · {title}\nStatus: {status}",
    "order_card_contact_creator": "👤 Creator: {contact}",
    "order_card_contact_client": "👤 Client: {contact}",
    "order_first_pay": "💳 Pay <b>50% prepayment</b> to:\n{details}",
    "order_second_pay": "💳 Pay <b>the remaining 50%</b> to:\n{details}",
    "ostatus_published": "🟣 published",
    "ostatus_taken": "🟡 taken, awaiting your confirmation",
    "ostatus_await_prepay": "💳 awaiting 50% prepayment",
    "ostatus_in_progress": "🔧 in progress",
    "ostatus_demo_review": "🔵 demo awaiting approval",
    "ostatus_await_final": "💳 awaiting final 50% payment",
    "ostatus_completed": "✅ completed",
    "ostatus_cancelled": "❌ cancelled",
    "btn_demo_done": "✅ Demo ready",
    "btn_approve_demo": "✅ Approve demo",
    "btn_paid": "💸 I have paid",
    "btn_republish": "♻️ Republish",
    "btn_orders_back": "⬅️ Back to list",
    "notify_creator_confirmed": "🙌 Client approved you for order #{order_id}. Awaiting prepayment.",
    "notify_demo_to_client": "🔔 Creator submitted a demo for order #{order_id} — review and approve.",
    "notify_demo_approved_creator": "🔔 Client approved the demo for order #{order_id}. Awaiting final payment.",
    "notify_paid_admin": "🔔 Client marked payment for order #{order_id}. Verify and confirm final.",
    "notify_republished": "♻️ Order #{order_id} republished to the creators chat.",
    "order_paid_waiting": "Noted. Wait for the admin to confirm the payment.",
    "profile_only_creator": "⛔ The cabinet is available only to approved creators.",
    "profile_title": (
        "👤 <b>Creator cabinet</b>\n\n"
        "Service: {service}\n"
        "Socials: {socials}\n"
        "Description: {desc}\n\n"
        "💵 Balance for payout: <b>{balance} ₽</b>"
    ),
    "btn_edit_socials": "🔗 Socials",
    "btn_edit_desc": "📝 Description",
    "btn_my_works": "🎵 My works",
    "btn_add_beat": "➕ Add beat",
    "profile_ask_socials": "Send your new social links in one message:",
    "profile_ask_desc": "Send your new description:",
    "profile_saved": "✅ Saved.",
    "add_beat_hint": "To add a beat, send the /addbeat command",
    "works_empty": "You have no uploaded works yet.",
    "works_list_title": "🎵 Your works (tap to edit):",
    "work_detail": (
        "🎵 <b>{title}</b>\n"
        "Genre: {genre} | Key: {key} | BPM: {bpm}\n"
        "💸 Rent: {rent} ₽ | 💰 Buyout: {buy} ₽\n"
        "Status: {status}"
    ),
    "btn_price_rent": "💸 Rent price",
    "btn_price_buy": "💰 Buyout price",
    "btn_delete_work": "🗑 Delete",
    "work_ask_price": "Enter the new price (number):",
    "work_price_invalid": "Enter the price as a number.",
    "work_price_updated": "✅ Price updated.",
    "work_deleted": "🗑 Work deleted.",
    "status_pending": "⏳ under moderation",
    "status_approved": "✅ in catalog",
    "status_rejected": "❌ rejected",
    "review_only_creator": "⛔ Only approved creators can upload reviews.",
    "review_ask_photo": "Send a screenshot of the review/chat with a happy client (photo):",
    "review_not_photo": "A photo is required. Send the screenshot as an image.",
    "review_saved": "✅ Thank you! The review is published in the SCREW PROD channel.",
    "review_saved_no_channel": "✅ Review saved (mirror channel not configured).",
    "reviews_intro": "💬 <b>SCREW PROD reviews</b>\nMirror channel: {url}",
    "reviews_empty": "💬 No reviews yet.\nMirror channel: {url}",
    "review_card": "💬 Review {pos}/{total}",
    "btn_reviews_channel": "📢 Open reviews channel",
    "review_prev": "⬅️",
    "review_next": "➡️",
    "review_upload_hint": "\n📸 Don't forget to upload a review: /review",
    "addwork_choose": "What to add to the catalog?",
    "addwork_beat": "🎧 Beat",
    "addwork_visual": "🖼 Visual",
    "addwork_only_creator": "⛔ Only approved creators can add works.",
    "addvisual_title": "🖼 Work title:",
    "addvisual_type": "Type (cover / banner / art / logo / 3D):",
    "addvisual_cover": "Send the work image (photo):",
    "addvisual_cover_invalid": "A photo is required. Send an image.",
    "addvisual_price_buy": "💰 Price (RUB):",
    "addvisual_sent": "✅ Visual sent for moderation.",
    "mod_new_visual": (
        "🆕 <b>New visual for moderation</b>\n\n"
        "Author: {author}\n"
        "Title: {title}\n"
        "Type: {vtype}\n"
        "Price: {buy} ₽"
    ),
    "work_approved_notify": "✅ Your work '{title}' is approved and added to the catalog.",
    "work_rejected_notify": "❌ Your work '{title}' was rejected by moderation.",
    "visual_card": (
        "🖼 <b>{title}</b>\n"
        "Author: {author}\n"
        "Type: {vtype}\n"
        "💰 Price: {buy} ₽\n"
        "({pos}/{total})"
    ),
    "filter_type": "Choose a type:",
}
