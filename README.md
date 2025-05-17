****USA Federal Agency Awards Data Pipeline****

**Data Source Used:**

For this project I utilized the USAspending API provided for free by the United States Federal Government. The primary data source was the /api/v2/agency/awards/count endpoint. The secondary data source used was the /api/v2/agency/{agency_code}/sub_components/ endpoint.

The data consists of each US Federal Agency, detailing the number of contracts given out, and the number of direct payments, grants, idvs, and loans received.

The second table consists of information regarding each Agency's subcomponents or sub-committees.


**Transformation Steps:**

The API endpoints provided challenging data to transform into a usable fashion. There were nested directories inside of other nested directories, and pages of data that I had not previously delt with. Using the fetch_all_agecny_awards_counts() function, I looped through each page of the API, storing the imortant data as needed. I looped through the whole object and returned a Pandas DateFrame with the necessary information.

Next, the same had to be done for the subcommittee data. This was even more complicated as each subcommittee had different pages, leading to a slightly more complicated looping process. This process used a while loop until the has_next variable became False.

In the load_database() function, I did additional cleaning to ensure the data was functionable. This included dropping duplicate values, ensuring there were no missing values, and transforming the Agency and SubCommittee classes into traditional Pandas DataFrames. This was done through a series of for loops that set the proper column names and ensured the correct types were used for each variable. 

The subcommittee information was harder to transform. I connected the SubCommittee class to the Agency class by using primary and foreign keys. The difficulty began when I realized not every agency had a subcommittee attached to it. This would create Nan values and end the execution of the database loading. First I had to ensure that the second data frame only provided rows that had a match in the first. Then the solution was to check if each value was Nan, and if it was, convert the value to 0.0. 

**Destination of the Data**

After the extraction and transformation steps, the dat awas loaded into a local SQLite database, stored through the app.db file. This utilized an SQLAlchemy ORM. The database contains two tables, easily queryable for both agency and subcommittee information. 

The database scheme uses a one-to-many relationship between the agencies and the subcommittees. Each agency could have multiple subcommittees assigned to it, but each subcommittee could only have one agency. 

The database can be accessed through a series of Flask API endpoints. A  user can retreive all subcommittees for a particular government agency, or reload the database from the API. I included a drop down menu for the users to make it easier to see the potential agencies. This data can be easily reused or analyzed by users due to the relational nature.

**Automation**

I unfortunately could not get the automation working properly. I was running into countless errors and frustrations. The ETL process is automated each time the Flask API endpoint is used. But Prefect and Airflow provided me much difficulty.
