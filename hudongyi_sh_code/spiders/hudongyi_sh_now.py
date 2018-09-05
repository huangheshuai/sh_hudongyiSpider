# -*- coding: utf-8 -*-
import scrapy
import re
import datetime
import logging
from fake_useragent import UserAgent
from hudongyi_sh_code.items import HudongyiShCodeItem
from hudongyi_sh_code.common import (
    question_datetime_parse,
    reply_datetime_parse,
    get_question_id,
)

from ..settings import SQL_DATETIME_FORMAT


logging.basicConfig(
    filename="hudongyi_sh.log",
    level=logging.INFO,
    format="%(asctime)-15s %(levelname)s %(filename)s %(lineno)d %(process)d %(message)s",
)


class HudongyiShSpider(scrapy.Spider):
    name = "hudongyi_sh_now"
    allowed_domains = ["sns.sseinfo.com"]
    # start_urls =[]
    dt = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    dt_now = datetime.datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")

    def start_requests(self):
        for pageNo in range(1,5):
            url = 'http://sns.sseinfo.com/ajax/feeds.do?type=11&pageSize=10&lastid=-1&show=1&page={0}&_=1532914493874'.format(pageNo)
            ua = UserAgent(use_cache_server=False)
            headers = {
                "Referer": "http://sns.sseinfo.com/",
                "User-Agent": ua.random,
            }
            yield scrapy.Request(
                url,
                headers=headers,
                callback=self.parse,
            )

    def parse(self, response):
        if (
            response.xpath('//div[@class="center"]/a/text()').extract_first()
            == "暂时没有问答"
        ):
            logging.info("暂时没有问答---no content")
            return

        result_list = response.xpath('//div[@class="m_feed_item"]')
        for result in result_list:
            txt_id = result.xpath('*//div[@class="m_feed_txt"]/@id').extract_first()
            # id
            question_id = txt_id.split("-")[-1]
            # 提问者
            questioner = result.xpath('*//a[@rel="face"]/@title').extract_first()
            # 公司简称
            shortName = (
                result.xpath('*//div[@class="m_feed_txt"]/a/text()')
                .extract_first()
                .split("(")[0]
                .replace(":", "")
                .replace("@", "")
                .strip()
            )
            # 公司代码
            stockCode = (
                result.xpath('*//div[@class="m_feed_txt"]/a/text()')
                .extract_first()
                .split("(")[1]
                .replace("(", "")
                .replace(")", "")
            )
            # 问题和答复 Question and answer --->QA
            QA_content = result.xpath('*//div[@class="m_feed_txt"]')
            if len(QA_content) == 2:
                q = QA_content[0].xpath(".//text()").extract()
                if q[0].startswith("\n\t"):
                    question_content = (
                        "".join(q[1:]).replace("\t", "").replace("\n", "")[1:]
                    )
                    reg = r"\d+(.*)"
                    question_content = (
                        re.findall(reg, question_content)[0]
                        .replace(")", "")
                        .replace("@", "")
                    )
                a = QA_content[1].xpath(".//text()").extract()
                reply_content = "".join(a).replace("\t", "").replace("\n", "")

            qt_and_at = result.xpath(
                './/div[@class="m_feed_from"]/span/text()'
            ).extract()
            if len(qt_and_at) == 2:
                # 提问时间 之前出现过带“年”的时间格式
                if "年" in qt_and_at[0]:
                    quetionTime = (
                        qt_and_at[0]
                        .replace("年", "-")
                        .replace("月", "-")
                        .replace("日", "")
                    )
                    quetionTime = datetime.datetime.strptime(
                        quetionTime, "%Y-%m-%d %H:%M"
                    )
                else:
                    # 提问时间格式化
                    question_timep = qt_and_at[0].replace("月", "-").replace("日", "")
                    quetionTime = datetime.datetime.strptime(
                        question_datetime_parse(question_timep), SQL_DATETIME_FORMAT
                    )

                # 回复时间
                if "年" in qt_and_at[1]:
                    replyTime = (
                        qt_and_at[1]
                        .replace("年", "-")
                        .replace("月", "-")
                        .replace("日", "")
                    )
                    replyTime = datetime.datetime.strptime(replyTime, "%Y-%m-%d %H:%M")
                else:
                    # 答复时间格式化
                    reply_timep = qt_and_at[1].replace("月", "-").replace("日", "")
                    replyTime = datetime.datetime.strptime(
                        reply_datetime_parse(reply_timep), SQL_DATETIME_FORMAT
                    )

            if replyTime > self.dt_now:
                logging.info("回复时间大于当前时间，时间解析失败")
                return

            Id = get_question_id(question_id)
            if Id:
                logging.info("本条问答已经入库，问答id为：{0}".format(Id))
                return

            db_write_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            item = HudongyiShCodeItem()
            item["questionId"] = question_id
            item["questioner"] = questioner
            item["questionTime"] = quetionTime
            item["questionContent"] = question_content
            item["replyTime"] = replyTime
            item["replyContent"] = reply_content
            item["stockCode"] = stockCode
            item["shortName"] = shortName
            item['db_write_time']=db_write_time
            yield item
