from . import phongvu, philong, mega, sp_one, buildcores

# Từ điển quản lý các site
SITES = {
    "1": ("Phong Vũ", phongvu.crawl),
    "2": ("Phi Long", philong.crawl),
    "3": ("Mega", mega.crawl),
    "4": ("SP-One", sp_one.crawl),
    "5": ("BuildCores", buildcores.crawl)
}