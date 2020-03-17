from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse
from common import init_logging
from pydantic import HttpUrl
from data.models import ArticleCached, CommentCached, ArticleScraped, CommentScraped, CommentedArticle, \
    ScrapeResultStatus, ScrapeResult, ScrapeResultDetails, CacheResult
from data.scrapers import get_matching_scraper, scrape, NoScraperException, ScraperWarning, NoCommentsWarning
from fastapi.responses import JSONResponse
from typing import Union
import data.database as db
import data.models as models
import data.cache as cache
from fastapi import Depends
from requests.exceptions import RequestException
import functools
import json

logger = init_logging('comex.api.route.platforms')
logger.debug('Setup comex.api.route.platforms router')

router = APIRouter()


def catch_scrape_errors(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except NoScraperException as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=ScrapeResultDetails(status=ScrapeResultStatus.NO_SCRAPER,
                                                           error=str(e)).__dict__)
        except NoCommentsWarning as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=ScrapeResultDetails(status=ScrapeResultStatus.NO_COMMENTS,
                                                           error=str(e)).__dict__)
        except (RequestException, ScraperWarning) as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=ScrapeResultDetails(status=ScrapeResultStatus.SCRAPER_ERROR,
                                                           error=str(e)).__dict__)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=ScrapeResultDetails(status=ScrapeResultStatus.ERROR,
                                                           error=str(e)).__dict__)

    return wrapper


@router.get('/scrape', response_model=ScrapeResult)
@catch_scrape_errors
async def direct_scrape(url: HttpUrl):
    article, comments = scrape(url)
    article = CommentedArticle(**article.dict(), comments=comments)
    return ScrapeResult(payload=article)


@router.get('/article', response_model=CacheResult,
            description='Try to get the article from the cache, '
                        'otherwise scrape, cache, and return article including comments.')
@catch_scrape_errors
# FIXME cache override and ignoring shouldn't be exposed!
async def get_article(url: HttpUrl, override_cache: bool = False, ignore_cache: bool = False):
    article = await cache.get_article(url, override_cache, ignore_cache)
    result = CacheResult(payload=article)
    return result
