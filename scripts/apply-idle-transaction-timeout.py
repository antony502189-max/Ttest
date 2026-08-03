from __future__ import annotations

import base64
import hashlib
import subprocess
import zlib
from pathlib import Path

EXPECTED_PATCH_SHA256 = "42a0fc6bbfc430c5b3499a783fbaf9d4c5a439c9519404cb147976a9a82c6d3b"
PATCH_ZLIB_BASE64 = """
eNq1V2tvo0YU/e5fMWKrbiwMAWz8Ur1ar8OHaBM7NU7bVVWhMVxsuhi8zJBHV/nvnQH8wDYTb6oSCYLn3DNw7zl3Bi/wfaQoi4AifDnH7leIvEu8Xl+6cQLsFPnBQl0/o7lgsBZEHjwh3dWgq+mq2nJbmml2ka5p7VarpiiKkLsmy7KY/+NHpBjtRhvJ7NxB7NYNMSHIBkqDaEEuPmECm5t6v4b44WGK5+x3Zx3HoZOA++yG4BBgtB7poyCiaIB0p6tpB3hCMYUVRNShwQrilDqrLb6tOdpRQBi7X09g9Rwrl7CBxx6CJjgi2KVBHL0yx9+PlD9yArSPCE3YqJSyUB8UDx4gjNf8OZUcobhLHC1AWYHSNKQ8HrsuEOLQmKXWWQVRSmH3fGaOScBPgCwLkIeft4imlqVeb+s893rbODv5myNOEIHQV4XFQL8g/ZWwUzU5I+ygMlmELIwQ1OcN830YnPEeO87D7K2TeB7CiqjME8waFzWvyq3e/JKwQrMHPjZraazwqtlpN5u+oaqm5vW6Ha/aq+XoY6uWxzO5aJlatFwsHvh71oLkARJ2KaSz+ae/VVMdKR+QF7j0Tyb3Btf8X/2NTGmaROj7LkXSUTalPvKl7xtWcdpfVkRq7JHt166K56C+OcVWUFImniAq6adIzmvMAt3tPehLDbG/kypgxqbkkvkWFgnmDNkvTlXqyzL58eBCR52O7pu9pqr6uDt3oXVaR2+gLwvtDQSZEnnDktlZ17kUMXmO3EyQWXR2u144rAdFkCWd8M4EwQM48ARumtVhnnoLoOQiE+Y4jqCQY072GNAlgmgRRKAWPAyJCdqR7nn6SIasx+JHzOq4g6vExSFOLig80QvJtm6s0Qy5aZLwsOIFL94fMb2vS/X6bqZ9ob55kn2SnH8r9Vyur/KXm614tjPMwx9iR1nnZuDHO3QXE7pIwP71BkVxssJh8A8QBN/S4AGHbBbELin7hcZoma5wpCSAPcx6K/IZnKibkjId0RNVCljbkXS2fEoNJLU1kl/YwZz5Uoot5T0Py+H6Fi7vwUtpFM8iMH3ZCwXdSYdXIjfLgqGD0WJbOKMzbzV7hsjO1VynvFuNzoza4haV+aW5WTSEDndSwk26DgM3YD0yCMMg30w4eaWP7LoJZGLdblx2dhEuFIOWyTdkjRPwg/Vg0HFMDpSPgIL2Puhpe/RbURcKeXXprKPB4NVFUWqZuY4EC57UMQvIjy5oUk8rseerFK9rs9cwkdzSd1uBrKpsX+OlOZsfhECcxyCBXa3FzbeUHulqOBt+GtqWY8+GM+vWGs+c2fWtNbmfObd2H/30XQxQMoO9SNx8brxaxwQq+G8mo89V1Idjin7MKp9kvb66sZzZdDi2h6PZ9WRcNYMId/47nErBIIvOguEJr9bhmQkY6EdxP/yKJ+YutTkP1mH8fLmTiwrRg1pAWYsRjm++SucGGJ6pqnNTcw0Tl1uamCFvZGJM9m1qZN+mxefR9s3vJpMbZ2qNvoxYBmxrNBlfsbRlH5zv0NXVTQM9LgN3iRL2SYfoMonTxRIN2YZ/HrjvCWtZa8x2O4D4ToONRnFKNnuNGjqjqHugk8WryecXqYbuhrb9+2R65bDTZ4e9zOh+OrXGoy8Do4Zuh384PPI3/qK2zRhs586aOve2NWWT5YBixLm27XsrH7+9Ht/PLI4oF561JkiUQs3qXuqfVyEviWi8KHyz67ahqamq62u97rx9UHghQ1F4IYYXvsfr3svL/qQUK57C5NFHP+/dcUcJVVHy+kmAwnXzUiL6Tx2vxPSG3sbN/n90Mf5clUrjZNWDipFFi6TICYTj7O22JJVy3bBUAzKafwHJpS4l
"""


def main() -> None:
    patch = zlib.decompress(base64.b64decode("".join(PATCH_ZLIB_BASE64.split())))
    if hashlib.sha256(patch).hexdigest() != EXPECTED_PATCH_SHA256:
        raise SystemExit("idle transaction timeout patch checksum mismatch")
    patch_path = Path(".idle-transaction-timeout.patch")
    patch_path.write_bytes(patch)
    subprocess.run(["git", "apply", "--check", str(patch_path)], check=True)
    subprocess.run(["git", "apply", str(patch_path)], check=True)
    patch_path.unlink()


if __name__ == "__main__":
    main()
