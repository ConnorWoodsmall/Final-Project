import requests
import pandas as pd
from flask import Flask, jsonify, request, current_app, g
from flask_sqlalchemy import SQLAlchemy
import numpy as np
import gzip
from io import BytesIO
from flasgger import Swagger
from sqlalchemy.orm import DeclarativeBase
import sqlite3
import os

app = Flask(__name__)

# Swagger configuration
app.config['SWAGGER'] = {
    'title': 'USA Federal Agency Awards API',
    'universion': 3
}
swagger = Swagger(app)

# Configure the databse URL
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
db = SQLAlchemy(app)

# Define a datbase model

class Agency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(), nullable=False)
    code = db.Column(db.Integer(), nullable=False)
    contracts = db.Column(db.Integer(), nullable=False)
    direct_payments = db.Column(db.Integer(), nullable=False)
    grants = db.Column(db.Integer(), nullable=False)
    idvs = db.Column(db.Integer(), nullable=False)
    loans = db.Column(db.Integer(), nullable=False)
    other = db.Column(db.Integer(), nullable=False)
    # Relationship to SubCommittee
    subcommittes = db.relationship('SubCommittee', backref='agency', lazy=True)

class SubCommittee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(), nullable=False)
    total_obligations = db.Column(db.Float(), nullable=False, default = 0.0)
    total_outlays = db.Column(db.Float(), nullable=False, default = 0.0)
    total_budgetary_resources = db.Column(db.Float(), nullable=False, default = 0.0)
    # Relationship to Agency
    agency_id = db.Column(db.Integer, db.ForeignKey('agency.id'), nullable=False)

# Create the database
with app.app_context():
    db.create_all()

# API endpoint to acquire agency award counts
def fetch_all_agency_award_counts(url, params=None):
    """
    Fetches all pages of agency award counts from the API and returns a pandas DataFrame.
    """
    if params is None:
        params = {}
    all_results = []
    page = 1
    has_next = True

    while has_next:
        params['page'] = page
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # The results are nested: results -> [ [ {...}, {...}, ... ] ]
        page_results = data.get('results', [[]])
        if page_results and isinstance(page_results[0], list):
            all_results.extend(page_results[0])
        elif page_results:
            all_results.extend(page_results)
        else:
            has_next = False

        page_metadata = data.get('page_metadata', {})
        if not page_metadata.get('hasNext', False):
            has_next = False

        page += 1

    return pd.DataFrame(all_results)

# API endpoint to acquire subcommittee information
def fetch_all_subcommittee_information(params=None):
    """
    Fetches all pages of subcommittee information from the API and returns a pandas DataFrame.
    """
    agency_code = params.pop('agency_code', None)
    url = f"https://api.usaspending.gov/api/v2/agency/{agency_code}/sub_components/"

    if params is None:
        params = {}
    all_results = []
    page = 1
    has_next = True

    while has_next:
        params['page'] = page
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # The results are nested: results -> [ [ {...}, {...}, ... ] ]
        page_results = data.get('results', [[]])
        if page_results and isinstance(page_results[0], list):
            all_results.extend(page_results[0])
        elif page_results:
            all_results.extend(page_results)
        else:
            has_next = False

        page_metadata = data.get('page_metadata', {})
        if not page_metadata.get('hasNext', False):
            has_next = False

        page += 1

    return pd.DataFrame(all_results)


@app.route('/reload', methods=['GET'])
def load_database():
    """
    Loads the database with agency award counts.
    ---
    responses:
        200:
            description: Database loaded successfully
    """
    url = "https://api.usaspending.gov/api/v2/agency/awards/count/" 
    df = fetch_all_agency_award_counts(url)
    df = df.drop_duplicates()
    df = df.dropna()
    db.session.query(Agency).delete() 
    db.session.query(SubCommittee).delete()
    for _, row in df.iterrows():
        agency = Agency(
            name = row['awarding_toptier_agency_name'],
            code = row['awarding_toptier_agency_code'],
            contracts = row['contracts'],
            direct_payments = row['direct_payments'],
            grants = row['grants'],
            idvs = row['idvs'],
            loans = row['loans'],
            other = row['other']
        )
        db.session.add(agency)
        db.session.commit()
        try:
            df2 = fetch_all_subcommittee_information(params={'agency_code': row['awarding_toptier_agency_code']})
            for _, row2 in df2.iterrows():
                print(row2['total_obligations'])
                subcommittee = SubCommittee(
                    name=row2['name'],
                    total_obligations=float(pd.to_numeric(row2['total_obligations'], errors='coerce')) if pd.notnull(row2['total_obligations']) else 0.0,
                    total_outlays=float(pd.to_numeric(row2['total_outlays'], errors='coerce')) if pd.notnull(row2['total_outlays']) else 0.0,
                    total_budgetary_resources=float(pd.to_numeric(row2['total_budgetary_resources'], errors='coerce')) if pd.notnull(row2['total_budgetary_resources']) else 0.0,
                    agency_id=agency.id
                )
                db.session.add(subcommittee)
            db.session.commit()
        except Exception as e:
            print(f"Error fetching subcommittee information for agency {agency.name}: {e}")
    # Generate summary statistics 
    summary = {
        "total_agencies": Agency.query.count(),
        "total_subcommittees": SubCommittee.query.count(),
    }

    return jsonify({"message": "Database loaded successfully"}, summary)


# I want the user to input an Agency name and get the subcommittes that match. Use docstrings to define the OpenAPI specs for Swagger UI
# @app.route('/get_subcommittees', methods=['GET'])
# def get_subcommittees():
#     """
#     Get subcommittees by agency name.
#     ---
#     parameters:
#         - name: agency_name
#           in: query
#           type: string
#           required: true
#           description: The name of the agency to search for.
#     responses:
#         200:
#             description: A list of subcommittees for the specified agency.
#             schema:
#                 type: array
#                 items:
#                     type: object
#                     properties:
#                         id:
#                             type: integer
#                             description: The ID of the subcommittee.
#                         name:
#                             type: string
#                             description: The name of the subcommittee.'
#     """
#     agency_name = request.args.get('agency_name')
#     if not agency_name:
#         return jsonify({"error": "Agency name is required"}), 400

#     subcommittees = SubCommittee.query.join(Agency).filter(Agency.name == agency_name).all()
#     result = [{"id": subcommittee.id, "name": subcommittee.name} for subcommittee in subcommittees]
    
#     return jsonify(result)

@app.route('/get_subcommittees', methods=['GET'])
def get_subcommittees():
    """
    Get subcommittees by agency name.
    ---
    parameters:
      - name: agency_name
        in: query
        type: string
        required: true
        description: The name of the agency to search for.
        enum:
          - Department of Defense
          - General Services Administration
          - Department of Agriculture
          - Department of Housing and Urban Development
          - Department of Veterans Affairs
          - Social Security Administration
          - Small Business Administration
          - Department of Health and Human Services
          - Department of Homeland Security
          - Railroad Retirement Board
          - Department of Transportation
          - Department of Justice
          - Department of Education
          - Department of State
          - Federal Communications Commission
          - Department of the Interior
          - National Aeronautics and Space Administration
          - Department of the Treasury
          - Department of Energy
          - Department of Commerce
          - Environmental Protection Agency
          - National Science Foundation
          - Department of Labor
          - Agency for International Development
          - Export-Import Bank of the United States
          - Smithsonian Institution
          - Securities and Exchange Commission
          - Corporation for National and Community Service
          - National Endowment for the Humanities
          - Federal Trade Commission
          - Nuclear Regulatory Commission
          - U.S. Agency for Global Media
          - National Endowment for the Arts
          - Pension Benefit Guaranty Corporation
          - National Archives and Records Administration
          - Government Accountability Office
          - Executive Office of the President
          - Consumer Financial Protection Bureau
          - Institute of Museum and Library Services
          - Equal Employment Opportunity Commission
          - Consumer Product Safety Commission
          - U.S. International Development Finance Corporation
          - National Gallery of Art
          - Office of Personnel Management
          - District of Columbia Courts
          - Millennium Challenge Corporation
          - Commodity Futures Trading Commission
          - Peace Corps
          - Denali Commission
          - Appalachian Regional Commission
          - Court Services and Offender Supervision Agency
          - Delta Regional Authority
          - Merit Systems Protection Board
          - International Trade Commission
          - National Labor Relations Board
          - Federal Mediation and Conciliation Service
          - National Transportation Safety Board
          - Gulf Coast Ecosystem Restoration Council
          - Federal Election Commission
          - Federal Maritime Commission
          - National Credit Union Administration
          - United States Trade and Development Agency
          - Federal Labor Relations Authority
          - United States Chemical Safety Board
          - Council of the Inspectors General on Integrity and Efficiency
          - Election Assistance Commission
          - Defense Nuclear Facilities Safety Board
          - Morris K. Udall and Stewart L. Udall Foundation
          - Library of Congress
          - Committee for Purchase from People Who Are Blind or Severely Disabled
          - Occupational Safety and Health Review Commission
          - Selective Service System
          - American Battle Monuments Commission
          - Federal Mine Safety and Health Review Commission
          - Federal Housing Finance Agency
    responses:
      200:
        description: A list of subcommittees for the specified agency.
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
                description: The ID of the subcommittee.
              name:
                type: string
                description: The name of the subcommittee.
              total_obligations:
                type: number
                description: The total obligations of the subcommittee.
              total_outlays:
                type: number
                description: The total outlays of the subcommittee.
              total_budgetary_resources:
                type: number
                description: The total budgetary resources of the subcommittee.
    """
    agency_name = request.args.get('agency_name')
    if not agency_name:
        return jsonify({"error": "Agency name is required"}), 400

    subcommittees = SubCommittee.query.join(Agency).filter(Agency.name == agency_name).all()
    result = [{
        "id": subcommittee.id,
        "name": subcommittee.name,
        "total_obligations": subcommittee.total_obligations,
        "total_outlays": subcommittee.total_outlays,
        "total_budgetary_resources": subcommittee.total_budgetary_resources
    } for subcommittee in subcommittees]
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)