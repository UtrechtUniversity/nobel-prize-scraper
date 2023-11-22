import argparse
import logging
import requests
import csv
import sqlite3
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

class NobelScraper:

    base_url='https://www.nobelprize.org/nomination/archive/list.php?prize={prize}&year={year}'
    nomination_url='https://www.nobelprize.org/nomination/archive/show.php?id={id}'

    min_year=1901
    max_year=2023
    prizes={
        1: 'Nobel Price in Physics',
        2: 'Nobel Price in Chemistry',
        3: 'Nobel Price in Physiology or Medicine',
        4: 'Nobel Price in Literature',
        5: 'Nobel Peace Price',
    }

    def __init__(self,
                 db_file=None,
                 min_year=None,
                 max_year=None
                 ):
        
        logging.basicConfig(level=logging.INFO)

        if min_year:
            self.min_year=min_year

        if max_year:
            self.max_year=max_year

        self.conn=self.connect_db(db_file)

    @staticmethod
    def connect_db(db_file):
        conn=None
        try:
            if db_file is None:
                conn=sqlite3.connect(':memory:')
            else:
                conn=sqlite3.connect(db_file)

            conn.execute("""CREATE TABLE  if not exists nominations (
                    id INTEGER PRIMARY KEY,
                    prize_id INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    nominees  TEXT NOT NULL,
                    nominators TEXT NOT NULL,
                    retrieved BOOL default false)""");

            conn.execute("""CREATE TABLE  if not exists nomination_people (
                    nomination_id INTEGER,
                    role  TEXT NOT NULL,
                    city  TEXT,
                    comments  TEXT,
                    country  TEXT,
                    gender  TEXT,
                    motivation  TEXT,
                    name  TEXT,
                    profession  TEXT,
                    state  TEXT,
                    university  TEXT,
                    year_birth  TEXT,
                    year_death  TEXT,
                    unique(nomination_id, role)
                );""")

            conn.row_factory=sqlite3.Row

        except Exception as e:
            logging.error("Error connecting or creating to database: %s" % str(e))
            raise e

        return conn

    def get_new_nominations(self):
        cursor=self.conn.cursor()
        cursor.execute("select * from nominations where retrieved=0 order by prize_id, year")
        nominations=[]
        for row in cursor.fetchall():
            nominations.append(row)

        return nominations
  
    def save_nomination(self, id, prize, year, nominees, nominators):
        cursor=self.conn.cursor()
        query="INSERT OR IGNORE INTO nominations (id, prize_id, year, nominees, nominators) VALUES (?,?,?,?,?)"
        data=(id, prize, year, nominees, nominators)
        cursor.execute(query, data)
        self.conn.commit()

    def save_nominations(self, prize, year, records):
        for record in records:
            self.save_nomination(
                id=record['id'],
                prize=prize, 
                year=year, 
                nominees=";".join([str(x[0]) for x in record['nominees']]),
                nominators=";".join([str(x[0]) for x in record['nominators']])
            )

    def save_nomination_info(self, nomination_id, info):

        cursor=self.conn.cursor()
        query="""INSERT OR IGNORE INTO nomination_people
            (nomination_id, role, city, comments, country, gender, motivation, name, profession, state, university, year_birth, year_death)
                VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        info_cols=['city', 'comments', 'country', 'gender', 'motivation', 'name', 'profession', 'state', 'university', 'year_birth', 'year_death']
        for role in info:
            data=(nomination_id, role, )
            for col in info_cols:
                val=[x[1] for x in info[role] if x[0]==col]
                data=data+((val[0], ) if len(val)>0 else (None,))
            
            cursor.execute(query, data)
            self.conn.commit()

    def export(self, filename='./out.csv'):

        def format_row(row):
            return [
                row['role'],
                row['name'],
                row['gender'],
                row['year_birth'],
                row['year_death'],
                row['profession'],
                row['university'],
                row['city'],
                row['state'],
                row['country'],
                row['motivation'],
                row['comments'],
            ]

        with open(filename, 'w') as file:
            csvwriter=csv.writer(file)
            csvwriter.writerow(['url', 'id', 'prize', 'year', 'role', 'name', 'gender', 'year_birth',
                                'year_death', 'profession', 'university', 'city', 'state', 'country',
                                'motivation', 'comments' ])

            records=self.get_records()
            for record in records:
                prize_fields=[self.nomination_url.format(id=record['id']), record['id'], record['prize'], record['year']]
                for nominee in record['nominees']:
                    row=prize_fields.copy()
                    row.extend(format_row(nominee))
                    csvwriter.writerow(row)
                for nominator in record['nominators']:
                    row=prize_fields.copy()
                    row.extend(format_row(nominator))
                    csvwriter.writerow(row)

        logging.info("Wrote data to '%s'" % filename)

    def get_records(self):
        cursor=self.conn.cursor()
        query="select * from nomination_people where nomination_id = ?"
        cursor.execute("select * from nominations order by prize_id, year, id")

        records=[]
        for row in cursor.fetchall():
            nomination={'year': row['year'], 'prize': self.prizes[row['prize_id']], 'id': row['id']}
            nominees=[]
            nominators=[]
            cursor.execute(query, (row['id'], ))
            for row2 in cursor.fetchall():
                 if row2['role'].find('Nominator')!=-1:
                    nominators.append(row2)
                 elif row2['role'].find('Nominee')!=-1:
                    nominees.append(row2)
            nomination.update({'nominees': nominees, 'nominators': nominators})
            records.append(nomination)

        return records

    def update_nomination(self, nomination_id):
        cursor=self.conn.cursor()
        cursor.execute("update nominations set retrieved=1 where id = ?", (nomination_id, ))
        self.conn.commit()

    def get_page(self, url):
        with requests.Session() as session:
            req=session.get(url)
            # print(dir(req))
            if req.status_code==200:
                return BeautifulSoup(req.content, "html.parser")

            raise ValueError("%s got http-code %s" % (url, req.status_code))
        
    def get_nominee_table(self, page):

        def parse_id_from_href(href):
            parsed_url=urlparse(href)
            query=parse_qs(parsed_url.query)
            if query['id'] and len(query['id'])>0:
                return int(query['id'][0])

        col1_head='Nominee(s)'
        col2_head='Nominator(s)'

        records=[]
        tables=page.find_all('table')

        for table in tables:
            nom_table=False

            body=table.find('tbody')
            if not body:
                body=table

            for rkey, row in enumerate(body.find_all('tr')):

                record={'id': None, 'nominees': [], 'nominators': []}

                for ckey, cell in enumerate(row.find_all('td')):

                    if rkey==0 and ckey==0 and cell.text.strip()==col1_head:
                        nom_table=True

                    if nom_table and rkey>0 and ckey in [0, 1, 2]:

                        if ckey==0 and len(cell.text.strip())>0:
                            nominees=[]
                            for link in cell.find_all('a'):
                                nominees.append((parse_id_from_href(link.get('href')),link.contents[0].strip()))
                            record.update({'nominees': nominees})
                        
                        if ckey==1 and len(cell.text.strip())>0:
                            nominators=[]    
                            for link in cell.find_all('a'):
                                nominators.append((parse_id_from_href(link.get('href')), link.contents[0].strip()))
                            record.update({'nominators': nominators})

                        if ckey==2 and len(cell.text.strip())>0:
                            link=cell.find('a')
                            
                            record.update({'id': parse_id_from_href(link.get('href'))})

                    if len(record['nominees'])>0 or len(record['nominators'])>0:
                        records.append(record)
        return records

    def get_nomination_info(self, page):

        def normalize_rubr(rubr):
            return rubr.text.strip().lower().replace(':','').replace(',','').replace(' ','_')

        table=page.find('table', attrs={'style':'border: 1px solid #DDDDDD;'})
        body=table.find('tbody')
        if not body:
            body=table
        
        data=[]
        subject=None
        for row in body.find_all('tr'):
            
            if len(row.text.strip())==0:
                continue

            header=row.find('b')
            if header:
                subject=header.text.replace(':','').strip()

            if subject:
                rubr=row.find('span', {'class': 'rubr'})
            
                if rubr and not header:
                    rubr=normalize_rubr(rubr)
                    cells=row.find_all('td')
                    val=cells[1].text.strip()
                    data.append((subject, rubr, val))

                elif not header:

                    cells=row.find_all('td')
                    
                    if len(cells)==1:
                        rubr='comments'
                        val=row.text.strip()
                    elif len(cells)>1:
                        rubr=normalize_rubr(cells[0])
                        if rubr=='comment':
                            rubr='comments'
                        val=cells[1].text.strip()
                    else:
                        continue

                    data.append((subject, rubr, val))

        nomination_info={}

        for item in data:
            if not item[0] in nomination_info:
                nomination_info[item[0]]=[]
            nomination_info[item[0]].append((item[1], item[2]))

        return nomination_info

    def scrape_overview(self):
        for prize in self.prizes:
            logging.info("Scraping '%s' overview" % self.prizes[prize])
            for year in range(self.min_year, self.max_year+1):
                url=self.base_url.format(prize=prize, year=year)
                logging.debug(url)
                page=self.get_page(url)
                records=self.get_nominee_table(page=page)
                logging.info("Year: %s; found %s lines" % (year, len(records)))
                self.save_nominations(prize=prize, year=year, records=records)

    def scrape_nominations(self):
        for nomination in self.get_new_nominations():
            logging.info("Scraping details for %s (%s, %s)" % (nomination['id'], self.prizes[nomination['prize_id']], nomination['year']))
            url=self.nomination_url.format(id=nomination['id'])
            logging.debug(url)
            page=self.get_page(url)
            info=self.get_nomination_info(page=page)
            self.save_nomination_info(nomination_id=nomination['id'], info=info)
            self.update_nomination(nomination_id=nomination['id'])

if __name__=="__main__":

    logging.basicConfig(level=logging.INFO)

    parser=argparse.ArgumentParser()
    parser.add_argument('--min-year', type=int, default=1901)
    parser.add_argument('--max-year', type=int, default=1971)
    parser.add_argument('--database-file', type=str)
    parser.add_argument('--output-file', type=str, default='./nobel.csv')
    args=parser.parse_args()

    scraper=NobelScraper(min_year=args.min_year, max_year=args.max_year, db_file=args.database_file)
    scraper.scrape_overview()
    scraper.scrape_nominations()
    scraper.export(filename=args.output_file)
