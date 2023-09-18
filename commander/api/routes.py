from fastapi import APIRouter
from starlette.status import HTTP_200_OK

router = APIRouter()


@router.get("/agents/count", status_code=HTTP_200_OK)
async def agents_count():
    # self.logger.core.info("Endpoint accessed: /agents/count")
    # return len(self.agents)
    return "Yes"
