import scrapy
import os
import sys
import requests
import tempfile


import django
from django.core import files
from scrapy_splash import SplashRequest

from ..utils.data_convertation import extract_singlenumber, extract_list_of_numbers

# Add django settings
django_path = "/".join(os.getcwd().split('/')[:-2]) + "/django"
sys.path.append(django_path)
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from accounts.models import Company, Review


class ClutchUrlsSpider(scrapy.Spider):
    name = "parse_clutch"

    def __init__(self, **kwargs):
        self.file = open('urls.txt', 'w+')
        self.companies = open('companies.csv', 'w+')
        super(ClutchUrlsSpider, self).__init__(**kwargs)

    def start_requests(self):

        urls = [
            'https://clutch.co/developers/python-django?page={}'.format(i) for i in range(1, 111)]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse_url)

        with open('urls.txt') as detail_urls:
            for url in detail_urls:
                url = url.replace('\n', '').replace('\r', '')
                # Check if we already have this url parsed
                # TODO: add option to bypass this condition in case we need to update parsed projects
                try:
                    Company.objects.get(parser_url=url)
                    continue
                except Company.DoesNotExist:
                    yield SplashRequest(url=url, callback=self.parse_page_details,
                                        meta={'url': url}, args={'wait': 3})

        companies = Company.objects.all()
        for company in companies:
            # Check if we already parsed reviews for selected company
            if Review.objects.filter(company=company).exists():
                continue
            company_url = company.parser_url
            for review_page_number in range(company.review_pages_number):
                review_url = company_url + "?page=0%2C" + str(review_page_number)
                yield SplashRequest(url=review_url, callback=self.parse_company_reviews,
                                    meta={'url': review_url, 'company': company}, args={'wait': 3})

    def is_unique(value, destination):
        for line in destination:
            if value in line:
                return False
        return True

    def parse_url(self, response):
        for h3 in response.css('h3.company-name'):
            link = "https://clutch.co{}".format(
                h3.css('a::attr(href)').extract_first())

            self.file.write(link + "\n")

    def download_image(self, image_url):
        request = requests.get(image_url, stream=True)
        # Get the filename from the url, used for saving later
        file_name = image_url.split('/')[-1].split('?', 1)
        # Create a temporary file
        lf = tempfile.NamedTemporaryFile()
        # Read the streamed image in sections
        for block in request.iter_content(1024 * 8):
            # If no more file then stop
            if not block:
                break
            # Write image block to temporary file
            lf.write(block)
        return file_name[0], files.File(lf)

    def parse_page_details(self, response):
        url = response.meta.get('url')
        title = response.css('h1.page-title::text').get().replace('\n', '')
        slogan = response.css(
            'div.field-item.even::text').get().replace('\n', '')
        description = ''.join(response.xpath(
            '//div[@property="description"]/..//text()').extract()).replace('READ MORE...', '')
        logo = response.css('div.logo-wrapper').css('img::attr(src)').get()
        rating = response.css('span.rating::text').get()
        try:
            reviews = response.css(
                'span.reviews-count').css('a::text').get().replace(' reviews ', '')
        except AttributeError:
            reviews = "0"

        website = response.css(
            'li.website-link-a').css('a::attr(href)').extract_first()
        try:
            website = website[0: website.index('?')]
        except:
            pass
        min_price = response.css(
            'div.field-name-field-pp-min-project-size').css('div.field-item::text').get()
        hourly_rates = extract_list_of_numbers(response.css(
            'div.field-name-field-pp-hrly-rate-range').css('div.field-item::text').get())
        try:
            hourly_max = hourly_rates[-1]
            if len(hourly_rates) > 1:
                hourly_min = hourly_rates[0]
            else:
                hourly_min = "0"
        except IndexError:
            pass

        people = response.css(
            'div.field-name-field-pp-size-people').css('div.field-item::text').get()
        founded = response.css(
            'div.field-name-field-pp-year-founded').css('div.field-item::text').get()
        try:
            location = response.css('span.location-name::text').extract()[1]
        except IndexError:
            location = ""

        phone = response.css('span.contact-dropdown-phone-ico::text').get()

        custom_dev = response.css(
            'div[data-content="Custom Software Development"]::text').get()
        mobile_dev = response.css(
            'div[data-content="Mobile App Development"]::text').get()
        ui_ux = response.css('div[data-content="UX/UI Design"]::text').get()
        web_dev = response.css(
            'div[data-content="Web Development"]::text').get()
        review_pages = response.xpath(
            '//*[@id="reviews"]/div/div/div[2]/div[2]/div[4]/ul/li[@class="pager-last"]/a/@href') \
            .get()
        if review_pages:
            try:
                review_pages = int(review_pages.rsplit('0%2C', 1)[-1]) + 1
            except ValueError:
                review_pages = 1
        else:
            review_pages = 1

        if title and slogan and description and phone and website and rating:

            company_dict = dict()
            company_dict['parser_url'] = url.strip()
            company_dict['name'] = title.strip()
            company_dict['slogan'] = slogan.strip()
            company_dict['description'] = description.strip()
            company_dict['rating'] = float(rating)
            company_dict['reviews'] = int(extract_singlenumber(reviews))
            company_dict['website'] = website.strip()
            company_dict['review_pages_number'] = review_pages

            if '$' in min_price:
                min_price = min_price.replace('$', '').replace(',', '').replace('+', '')
            if min_price == 'Undisclosed':
                min_price = 0

            company_dict['min_price'] = float(min_price)
            company_dict['hourly_min'] = int(hourly_min.replace('$', ''))
            company_dict['hourly_max'] = int(hourly_max.replace('$', ''))
            company_dict['people'] = people.strip()
            if founded:
                company_dict['founded'] = int(founded)
            else:
                company_dict['founded'] = 0
            company_dict['location'] = location.strip()
            company_dict['phone'] = phone.strip()

            if custom_dev:
                company_dict['custom_dev'] = int(custom_dev.replace('%', ''))
            if mobile_dev:
                company_dict['mobile_dev'] = int(mobile_dev.replace('%', ''))
            if ui_ux:
                company_dict['ui_ux'] = int(ui_ux.replace('%', ''))
            if web_dev:
                company_dict['web_dev'] = int(web_dev.replace('%', ''))

            company = Company.objects.get_or_create(name=company_dict['name'], defaults=company_dict)[0]

            if logo:
                image_name, image_file = self.download_image(logo)
                company.logo.save(image_name, image_file)
                company.save()

    def parse_company_reviews(self, response):
        url = response.meta.get('url')
        company = response.meta.get('company')

        reviews = response.xpath('//*[@id="reviews"]/div/div/div[2]/div[2]/div[3]/div[contains(@class, "views-row")]')
        for review in reviews:
            review_dict = dict()
            # Get closer to our desired data
            review_clearfix = review.xpath('div/div[1]/div/div')
            # Data separated into 3 columns, get their selectors
            review_column1 = review_clearfix.xpath('div[2]')
            review_column2 = review_clearfix.xpath('div[4]')
            review_column3 = review_clearfix.xpath('div[3]')
            # Extract data from selector columns
            review_dict['project_name'] = review_column1.xpath('h2/a/text()').get()
            review_dict['reviewer_company_name'] = review_column3.xpath('div/div[1]/div/div[1]/div/div/text()').get()
            review_dict['category'] = review_column1.xpath('div[2]/div[1]/div[2]/div/text()').get()
            review_dict['price_range'] = review_column1.xpath('div[2]/div[2]/div[2]/div/text()').get()
            review_dict['project_length'] = review_column1.xpath('div[2]/div[3]/div[2]/div/text()').get()
            review_dict['project_summary'] = review_column1.xpath('div[4]/div[5]/div[2]/div/p/text()').get()
            review_dict['average_feedback_rating'] = review_column2.xpath('div[1]/div[1]/div/div[1]/div/div/div/div/div/p/span/text()').get()
            review_dict['feedback_summary'] = review_column2.xpath('div[4]/div[2]/div/p/text()').get()
            review_dict['industries'] = review_column3.xpath('div/div[2]/div[2]/div/text()').get()
            review_dict['number_of_employees'] = review_column3.xpath('div/div[contains(@class, "field-name-field-fdb-company-size")]/div[2]/div/text()').get()
            review_dict['location'] = review_column3.xpath('div/div[contains(@class, "field-name-field-fdb-location")]/div[2]/div/text()').get()
            if review_column3.xpath('div/div[contains(@class, "field-name-field-fdb-verified")]/div[2]/div/text()').get().lower() == 'verified':
                review_dict['verified'] = True
            else:
                review_dict['verified'] = False

            Review.objects.get_or_create(company=company,
                                         project_name=review_dict['project_name'],
                                         defaults=review_dict)


# Run splash with:
# sudo docker run -it -p 8050:8050 --rm scrapinghub/splash