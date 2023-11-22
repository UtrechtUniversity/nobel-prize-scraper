# Nobel Prize nominations scraper

Script scrapes data from historical Nobel Prize nominations from the archive on [nobelprize.org](https://www.nobelprize.org/nomination/archive/) in the five categories:

+ Nobel Peace Price
+ Nobel Price in Chemistry
+ Nobel Price in Literature
+ Nobel Price in Physics
+ Nobel Price in Physiology or Medicine

Data is available from 1901 up to 1971; later years are not in the archive.

From the markup of the archive's pages, it is not always possible to automatically determine whether the two fields with extra information, _motivation_ and _comments_, belong with the nominator or nominee, or are general remarks. As a result, some of the comments may end up with a specific person, while they are general in nature (such as 'The nomination was divided between P. Lenard and W.C. Röntgen.').


## How to run
Basic use: 
```bash 
python main.py
```

Available arguments:
```bash
  --min-year MIN_YEAR (defaults to 1901)
  --max-year MAX_YEAR (defaults to 1971)
  --database-file DATABASE_FILE (defaults to None; see below)
  --output-file OUTPUT_FILE (defaults to './nobel.csv')
```

For example, to scrape data for the period 1960-1970, using a persistent database called 'nobel.db3', and save it to a file called 'novel_sixties.csv', run:
```bash
python main.py \
    --min-year 1960 \
    --max-year 1970 \
    --output-file ./novel_sixties.csv \
    --database-file ./nobel.db3
```

## Database

By default, the script uses an in-memory database to save the scraped data, which is automatically destroyed after the script finishes. This means that if you re-run the script, the scraping process starts again from scratch. To avoid, run the script with a named database file, so that the database is created and saved to disk. When re-running the script, specify the same database file, so that entries that were scraped before are not scraped again.


## Output
Output is a CSV-file with the details from listed nominations. One nomination can have muiltiple nominators and nominees. A common value in the column 'id' indicates that rows belong together as a set of nominators and nominees.
 

