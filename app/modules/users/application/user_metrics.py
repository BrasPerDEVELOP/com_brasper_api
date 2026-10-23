from collections import Counter, defaultdict

# Códigos nacionales de Brasil (Anatel). El 61 incluye DF y parte de Goiás.
BRAZIL_DDDS = set("11 12 13 14 15 16 17 18 19 21 22 24 27 28 31 32 33 34 35 37 38 41 42 43 44 45 46 47 48 49 51 53 54 55 61 62 63 64 65 66 67 68 69 71 73 74 75 77 79 81 82 83 84 85 86 87 88 89 91 92 93 94 95 96 97 98 99".split())


def summarize_user_metrics(rows):
    total = active = brazil = located = 0
    countries = Counter()
    areas = Counter()
    area_names = defaultdict(set)
    for row in rows:
        count = int(row["total"])
        total += count
        active += int(row["enabled"] or 0)
        country = row["country"] or "sin-pais"
        is_brazil = country in {"brasil", "brazil", "br", "bra"} or (
            country == "sin-pais" and row["phone_code"] in {"55", "+55"}
        )
        countries["Brasil" if is_brazil else country] += count
        if not is_brazil:
            continue
        brazil += count
        code = row["area"]
        if code in BRAZIL_DDDS:
            located += count
            areas[code] += count
            if row["name"]:
                area_names[code].add(row["name"])
    return {
        "total": total, "active": active, "brazil": brazil,
        "brazil_located": located, "brazil_missing_area": brazil - located,
        "countries": [{"name": name, "count": count} for name, count in countries.most_common()],
        "areas": [
            {"code": code, "name": " / ".join(sorted(area_names[code])) or f"Área DDD {code}",
             "count": count, "percentage": round(count * 100 / brazil, 2) if brazil else 0}
            for code, count in sorted(areas.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


class GetUserMetricsUseCase:
    def __init__(self, repository):
        self.repository = repository

    async def execute(self, role=None):
        return summarize_user_metrics(await self.repository.grouped(role=role))
