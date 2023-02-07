import matplotlib.pyplot as plt
import math

# discounts = []
# MAX = 100
# NUMERATOR = 1000

# for i in range(1,MAX):
#     discounts.append(1.0 / (1.0 + (9.9999 * (math.e ** (4.6969 * (i / MAX - 1))))))

# fig, ax = plt.subplots()

# ax.plot(range(1, 100), discounts, linewidth=2.0)

# plt.show()

discounts = []
MAX = 500
NUMERATOR = 10000
import math

for i in range(1, MAX + 1):
    print(i)
    d = 1.0 / (1.0 + (9.9999 * (math.e ** (4.6969 * (i / MAX - 1)))))
    discounts.append(int(d * NUMERATOR))

total_supply = 10**20
usd_price = 7_500
print("YFI price: {usd_price} USD")
for i in range(1, 100):
    total_locked = 10**18 * i
    discount = discounts[int(total_locked * MAX / total_supply)]
    price = 10**18 * (NUMERATOR - discount) / NUMERATOR
    print(
        f"with {i} percent locked, 1oYFI can be exchange for 1YFI at price: {price / 10**18 * usd_price} usd"
    )
