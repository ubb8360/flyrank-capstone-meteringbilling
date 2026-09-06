import logging

from app.jobs.usage_recon import (
    run_with_retries,
)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    run_with_retries()