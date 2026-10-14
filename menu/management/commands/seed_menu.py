"""Idempotent menu seed — mirrors frontend mockFoods + mockPackages. Re-run safe."""

from django.core.management.base import BaseCommand

from menu.models import FoodItem, Package, PackageItem

FOODS = [
    ("food_001", "Chicken Burger", "Burger", 320, "https://images.unsplash.com/photo-1568909344668-6f14a07b56a0?w=500", True),
    ("food_002", "Beef Cheese Burger", "Burger", 380, "https://images.unsplash.com/photo-1550547660-d9450f859349?w=500", True),
    ("food_003", "Margherita Pizza", "Pizza", 650, "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=500", True),
    ("food_004", "Pepperoni Pizza", "Pizza", 750, "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=500", True),
    ("food_005", "Chicken Biryani", "Biryani", 450, "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=500", True),
    ("food_006", "Mutton Biryani", "Biryani", 550, "https://images.unsplash.com/photo-1589302168068-964664d93dc0?w=500", False),
    ("food_007", "Chocolate Cake", "Dessert", 220, "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=500", True),
    ("food_008", "Chicken Shawarma", "Burger", 280, "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=500", True),
    ("food_009", "BBQ Chicken Pizza", "Pizza", 800, "https://images.unsplash.com/photo-1593560708920-61dd98c46a4e?w=500", True),
    ("food_010", "Kheer", "Dessert", 150, "https://images.unsplash.com/photo-1488477181946-64290103bb53?w=500", True),
    ("food_011", "Fried Rice with Chicken", "Biryani", 380, "https://images.unsplash.com/photo-1512058564366-18510be2db19?w=500", True),
    ("food_012", "Ice Cream Sundae", "Dessert", 180, "https://images.unsplash.com/photo-1497034825429-c343d7c6a68f?w=500", True),
    ("food_013", "Mineral Water 500ml", "Drinks", 20, "https://images.unsplash.com/photo-1523362628745-0c100150b504?w=500", True),
    ("food_014", "Coca-Cola 500ml", "Drinks", 40, "https://images.unsplash.com/photo-1554866585-cd94860890b7?w=500", True),
    ("food_015", "Mojo 500ml", "Drinks", 40, "https://images.unsplash.com/photo-1581636625402-29b2a704ef13?w=500", True),
    ("food_016", "SevenUp 500ml", "Drinks", 40, "https://images.unsplash.com/photo-1621263764928-df1444c5e859?w=500", True),
    ("food_017", "Fanta 500ml", "Drinks", 45, "https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=500", True),
    ("food_018", "Dudh Cha", "Drinks", 20, "https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=500", True),
    ("food_025", "Coca-Cola 250ml", "Drinks", 25, "https://images.unsplash.com/photo-1554866585-cd94860890b7?w=500", True),
    ("food_026", "Mojo 250ml", "Drinks", 25, "https://images.unsplash.com/photo-1581636625402-29b2a704ef13?w=500", True),
    ("food_027", "SevenUp 250ml", "Drinks", 25, "https://images.unsplash.com/photo-1621263764928-df1444c5e859?w=500", True),
    ("food_028", "Fanta 250ml", "Drinks", 30, "https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=500", True),
    ("food_019", "Fresh Orange Juice", "Juice", 80, "https://images.unsplash.com/photo-1544145945-f90425340c7e?w=500", True),
    ("food_020", "Mango Juice", "Juice", 100, "https://images.unsplash.com/photo-1546173159-315724a31696?w=500", True),
    ("food_021", "Lemon-Mint Juice", "Juice", 60, "https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=500", True),
    ("food_022", "Mixed Fruit Juice", "Juice", 90, "https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=500", True),
    ("food_023", "Sweet Lassi", "Juice", 70, "https://images.unsplash.com/photo-1610970881699-44a5587cabec?w=500", True),
    ("food_024", "Banana Milkshake", "Juice", 120, "https://images.unsplash.com/photo-1577805947697-89e18249d767?w=500", True),
]

PACKAGES = [
    {
        "id": "pkg_001",
        "name": "Lunch Package",
        "price": 550,
        "offer_price": 499,
        "offer_note": "Dupur Offer",
        "image": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=500",
        "active": True,
        "items": [("food_005", 1), ("food_010", 1)],
    },
    {
        "id": "pkg_002",
        "name": "Burger Combo",
        "price": 450,
        "offer_price": None,
        "offer_note": None,
        "image": "https://images.unsplash.com/photo-1568909344668-6f14a07b56a0?w=500",
        "active": True,
        "items": [("food_001", 1), ("food_012", 1)],
    },
]


class Command(BaseCommand):
    help = "Seed menu (foods + packages). Safe to re-run."

    def handle(self, *args, **options):
        for fid, name, category, price, image, available in FOODS:
            FoodItem.objects.update_or_create(
                id=fid,
                defaults={
                    "name": name,
                    "category": category,
                    "price": price,
                    "image": image,
                    "available": available,
                },
            )
        for pkg in PACKAGES:
            package, _ = Package.objects.update_or_create(
                id=pkg["id"],
                defaults={
                    "name": pkg["name"],
                    "price": pkg["price"],
                    "offer_price": pkg["offer_price"],
                    "offer_note": pkg["offer_note"],
                    "image": pkg["image"],
                    "active": pkg["active"],
                },
            )
            package.items.all().delete()
            PackageItem.objects.bulk_create(
                [
                    PackageItem(package=package, food_id=fid, qty=qty)
                    for fid, qty in pkg["items"]
                ]
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"seeded {FoodItem.objects.count()} foods, {Package.objects.count()} packages"
            )
        )
