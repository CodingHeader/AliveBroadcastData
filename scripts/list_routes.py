import sys
sys.path.insert(0, 'E:/Code/AliveBroadcastData/server')

from routers import admin
routes = []
for route in admin.router.routes:
    routes.append(f"{route.methods} {route.path}")

for r in sorted(routes):
    print(r)