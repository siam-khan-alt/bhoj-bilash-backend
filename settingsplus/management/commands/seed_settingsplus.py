"""Idempotent settings seed — singleton config + 7 hours + 19 option rows. Re-run safe."""

from django.core.management.base import BaseCommand

from settingsplus.models import OpeningHours, OptionList, RestaurantConfig, Review
from settingsplus.views import DEFAULT_HOURS

OPTIONS = [
    ("opt_fc_1", "food_category", "Burger", "বার্গার", "Burger", 1),
    ("opt_fc_2", "food_category", "Pizza", "পিজ্জা", "Pizza", 2),
    ("opt_fc_3", "food_category", "Biryani", "বিরিয়ানি", "Biryani", 3),
    ("opt_fc_4", "food_category", "Dessert", "ডেজার্ট", "Dessert", 4),
    ("opt_fc_5", "food_category", "Drinks", "পানীয়", "Drinks", 5),
    ("opt_fc_6", "food_category", "Juice", "জুস", "Juice", 6),
    ("opt_sj_1", "staff_job", "baburchi", "বাবুর্চি", "Baburchi", 1),
    ("opt_sj_2", "staff_job", "helper", "হেলপার", "Helper", 2),
    ("opt_sj_3", "staff_job", "cashier", "ক্যাশিয়ার", "Cashier", 3),
    ("opt_sj_4", "staff_job", "other", "অন্য", "Other", 4),
    ("opt_eh_1", "expense_head", "bazar", "বাজার (কাঁচামাল)", "Bazar (raw market)", 1),
    ("opt_eh_2", "expense_head", "salary", "বেতন / অগ্রিম", "Salary / Advance", 2),
    ("opt_eh_3", "expense_head", "rent", "দোকান ভাড়া", "Shop rent", 3),
    ("opt_eh_4", "expense_head", "utility", "কারেন্ট / গ্যাস / পানি", "Power / Gas / Water", 4),
    ("opt_eh_5", "expense_head", "other", "অন্য", "Other", 5),
    ("opt_pm_1", "payment_method", "cash", "ক্যাশ", "Cash", 1),
    ("opt_pm_2", "payment_method", "card", "কার্ড", "Card", 2),
    ("opt_ds_1", "drink_size", "250ml", "২৫০ মিলি", "250ml", 1),
    ("opt_ds_2", "drink_size", "500ml", "৫০০ মিলি", "500ml", 2),
    ("opt_ds_3", "drink_size", "1L", "১ লিটার", "1L", 3),
]

REVIEWS = [
    ("rev_001", "Karim Uddin", 5, "Biryani ta gorom gorom paisi — ei dam e er cheye valo hoy na."),
    ("rev_002", "Sharmin Akter", 5, "Bacchader niye boshe khaisi, khabar o taratari asche."),
    ("rev_003", "Rafiq Hasan", 4, "Juice fresh chilo, dam thik ache. Biryani aro jhal hole valo hoto."),
]


class Command(BaseCommand):
    help = "Seed shop config + hours + option lists + demo reviews. Safe to re-run."

    def handle(self, *args, **options):
        RestaurantConfig.objects.update_or_create(
            id=1,
            defaults={
                "slug": "bhoj-bilash",
                "name": "Bhoj Bilash",
                "logo": "/logo.png",
                "address": "Dhaka, Bangladesh",
                "phone": "+880 1700-000001",
            },
        )
        for i, (o, c) in enumerate(DEFAULT_HOURS):
            OpeningHours.objects.update_or_create(
                weekday=i,
                defaults={"open_time": o, "close_time": c, "closed": False},
            )
        for oid, key, value, bn, en, sort in OPTIONS:
            OptionList.objects.update_or_create(
                id=oid,
                defaults={
                    "list_key": key,
                    "value": value,
                    "label_bn": bn,
                    "label_en": en,
                    "sort_order": sort,
                    "active": True,
                },
            )
        for rid, name, rating, text in REVIEWS:
            Review.objects.update_or_create(
                id=rid, defaults={"name": name, "rating": rating, "text": text}
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"seeded config + {OpeningHours.objects.count()} days + "
                f"{OptionList.objects.count()} options + {Review.objects.count()} reviews"
            )
        )
