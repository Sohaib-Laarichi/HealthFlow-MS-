import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, Input, Output, callback, dash_table
import dash_bootstrap_components as dbc
import psycopg2
import psycopg2.extras
from sklearn.metrics import confusion_matrix, classification_report
from evidently import ColumnMapping
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, DataQualityPreset

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database Configuration
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'postgres')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'healthflow')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'healthflow')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'healthflow123')

class AuditFairnessAnalyzer:
    """
    Analyzer for model fairness and data drift monitoring
    """
    
    def __init__(self):
        self.db_connection = None
        self.connect_to_database()
    
    def connect_to_database(self):
        """Connect to PostgreSQL database"""
        try:
            self.db_connection = psycopg2.connect(
                host=POSTGRES_HOST,
                database=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            logger.info("Connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def get_prediction_data(self, days_back: int = 7) -> pd.DataFrame:
        """Get prediction data from database"""
        try:
            query = """
                SELECT 
                    patient_pseudo_id,
                    risk_score,
                    prediction_confidence,
                    shap_values_json,
                    feature_vector_json,
                    model_version,
                    prediction_timestamp,
                    created_at
                FROM prediction_results 
                WHERE prediction_timestamp >= NOW() - INTERVAL '%s days'
                ORDER BY prediction_timestamp DESC
            """
            
            with self.db_connection.cursor() as cursor:
                cursor.execute(query, (days_back,))
                results = cursor.fetchall()
            
            df = pd.DataFrame(results)
            if not df.empty:
                df['prediction_timestamp'] = pd.to_datetime(df['prediction_timestamp'])
                df['created_at'] = pd.to_datetime(df['created_at'])
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching prediction data: {e}")
            return pd.DataFrame()
    
    def extract_features_from_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract features from feature_vector_json column"""
        if df.empty or 'feature_vector_json' not in df.columns:
            return pd.DataFrame()
        
        try:
            features_list = []
            for _, row in df.iterrows():
                if row['feature_vector_json']:
                    features = json.loads(row['feature_vector_json'])
                    features['patient_pseudo_id'] = row['patient_pseudo_id']
                    features['risk_score'] = row['risk_score']
                    features['prediction_timestamp'] = row['prediction_timestamp']
                    features_list.append(features)
            
            if features_list:
                features_df = pd.DataFrame(features_list)
                return features_df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return pd.DataFrame()
    
    def analyze_fairness_by_demographics(self, features_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze fairness across demographic groups"""
        if features_df.empty:
            return {}
        
        try:
            fairness_analysis = {}
            
            # Gender fairness analysis
            if 'gender_male' in features_df.columns and 'gender_female' in features_df.columns:
                features_df['gender'] = features_df.apply(
                    lambda row: 'male' if row.get('gender_male', 0) == 1 
                    else 'female' if row.get('gender_female', 0) == 1 
                    else 'unknown', axis=1
                )
                
                gender_stats = features_df.groupby('gender')['risk_score'].agg([
                    'count', 'mean', 'std', 'min', 'max'
                ]).round(3)
                fairness_analysis['gender'] = gender_stats.to_dict('index')
            
            # Age group fairness analysis
            if 'age' in features_df.columns:
                features_df['age_group'] = pd.cut(
                    features_df['age'], 
                    bins=[0, 30, 50, 65, 100], 
                    labels=['young', 'middle', 'senior', 'elderly']
                )
                
                age_stats = features_df.groupby('age_group')['risk_score'].agg([
                    'count', 'mean', 'std', 'min', 'max'
                ]).round(3)
                fairness_analysis['age_group'] = age_stats.to_dict('index')
            
            # Calculate disparate impact
            if 'gender' in features_df.columns:
                high_risk_threshold = 0.7
                male_high_risk_rate = (
                    features_df[features_df['gender'] == 'male']['risk_score'] >= high_risk_threshold
                ).mean()
                female_high_risk_rate = (
                    features_df[features_df['gender'] == 'female']['risk_score'] >= high_risk_threshold
                ).mean()
                
                if female_high_risk_rate > 0:
                    disparate_impact = male_high_risk_rate / female_high_risk_rate
                    fairness_analysis['disparate_impact'] = {
                        'male_high_risk_rate': male_high_risk_rate,
                        'female_high_risk_rate': female_high_risk_rate,
                        'disparate_impact_ratio': disparate_impact,
                        'is_fair': 0.8 <= disparate_impact <= 1.25  # Common fairness threshold
                    }
            
            return fairness_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing fairness: {e}")
            return {}
    
    def analyze_data_drift(self, features_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze data drift using Evidently"""
        if features_df.empty or len(features_df) < 2:
            return {}
        
        try:
            # Split data into reference (older) and current (newer)
            features_df_sorted = features_df.sort_values('prediction_timestamp')
            split_point = len(features_df_sorted) // 2
            
            reference_data = features_df_sorted.iloc[:split_point]
            current_data = features_df_sorted.iloc[split_point:]
            
            if len(reference_data) < 10 or len(current_data) < 10:
                return {'status': 'insufficient_data'}
            
            # Select numeric features for drift analysis
            numeric_features = features_df.select_dtypes(include=[np.number]).columns.tolist()
            numeric_features = [col for col in numeric_features if col not in ['risk_score', 'patient_pseudo_id']]
            
            if not numeric_features:
                return {'status': 'no_numeric_features'}
            
            # Create Evidently report
            column_mapping = ColumnMapping()
            column_mapping.target = 'risk_score'
            column_mapping.numerical_features = numeric_features[:20]  # Limit to avoid memory issues
            
            drift_report = Report(metrics=[DataDriftPreset(), DataQualityPreset()])
            
            # Prepare data for Evidently
            ref_data = reference_data[numeric_features + ['risk_score']].fillna(0)
            cur_data = current_data[numeric_features + ['risk_score']].fillna(0)
            
            drift_report.run(
                reference_data=ref_data,
                current_data=cur_data,
                column_mapping=column_mapping
            )
            
            # Extract key metrics from the report
            report_dict = drift_report.as_dict()
            
            drift_analysis = {
                'status': 'completed',
                'reference_period': reference_data['prediction_timestamp'].min().strftime('%Y-%m-%d'),
                'current_period': current_data['prediction_timestamp'].max().strftime('%Y-%m-%d'),
                'reference_size': len(reference_data),
                'current_size': len(current_data),
                'features_analyzed': len(numeric_features)
            }
            
            # Extract drift metrics if available
            if 'metrics' in report_dict:
                for metric in report_dict['metrics']:
                    if metric.get('metric') == 'DatasetDriftMetric':
                        drift_analysis['dataset_drift_detected'] = metric.get('result', {}).get('drift_detected', False)
                        drift_analysis['drift_score'] = metric.get('result', {}).get('drift_score', 0)
            
            return drift_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing data drift: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def calculate_model_performance_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate model performance metrics"""
        if df.empty:
            return {}
        
        try:
            metrics = {}
            
            # Basic statistics
            metrics['total_predictions'] = len(df)
            metrics['mean_risk_score'] = df['risk_score'].mean()
            metrics['std_risk_score'] = df['risk_score'].std()
            metrics['mean_confidence'] = df['prediction_confidence'].mean() if 'prediction_confidence' in df.columns else None
            
            # Risk distribution
            risk_distribution = pd.cut(
                df['risk_score'], 
                bins=[0, 0.3, 0.6, 0.8, 1.0], 
                labels=['Low', 'Moderate', 'High', 'Critical']
            ).value_counts().to_dict()
            metrics['risk_distribution'] = risk_distribution
            
            # Temporal trends
            if 'prediction_timestamp' in df.columns:
                daily_stats = df.set_index('prediction_timestamp').resample('D')['risk_score'].agg([
                    'count', 'mean', 'std'
                ]).fillna(0)
                metrics['daily_trends'] = daily_stats.to_dict('index')
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {}

# Initialize the analyzer
analyzer = AuditFairnessAnalyzer()

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.MINTY])
app.title = "HealthFlow Audit & Fairness Dashboard"

# Navbar
navbar = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand("HealthFlow • Audit & Fairness", className="fw-bold"),
        dbc.Nav(
            [
                dbc.NavItem(dbc.NavLink("Docs", href="https://github.com/your-org/HealthFlow-MS", target="_blank")),
                dbc.NavItem(dbc.NavLink("ScoreAPI", href="http://localhost:8082/docs", target="_blank")),
            ], navbar=True
        ),
    ]),
    color="primary",
    dark=True,
    className="mb-4 shadow"
)

# Define the layout
app.layout = dbc.Container([
    navbar,

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Time Period", className="fw-semibold"),
                dbc.CardBody([
                    dcc.Dropdown(
                        id='time-period-dropdown',
                        options=[
                            {'label': 'Last 24 hours', 'value': 1},
                            {'label': 'Last 3 days', 'value': 3},
                            {'label': 'Last 7 days', 'value': 7},
                            {'label': 'Last 14 days', 'value': 14},
                            {'label': 'Last 30 days', 'value': 30}
                        ],
                        value=7,
                        placeholder="Select time period"
                    ),
                    dcc.Loading(html.Div(id="data-summary", className="mt-3"), type="dot")
                ])
            ], className="shadow-sm")
        ], width=4),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Model Performance Overview", className="fw-semibold"),
                dbc.CardBody([
                    dcc.Loading(html.Div(id="performance-metrics"), type="dot")
                ])
            ], className="shadow-sm")
        ], width=8)
    ], className="mb-4 g-4"),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Risk Score Distribution", className="fw-semibold"),
                dbc.CardBody([
                    dcc.Loading(dcc.Graph(id="risk-distribution-chart"), type="cube")
                ])
            ], className="shadow-sm h-100")
        ], width=6),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Temporal Trends", className="fw-semibold"),
                dbc.CardBody([
                    dcc.Loading(dcc.Graph(id="temporal-trends-chart"), type="cube")
                ])
            ], className="shadow-sm h-100")
        ], width=6)
    ], className="mb-4 g-4"),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Fairness Analysis", className="fw-semibold"),
                dbc.CardBody([
                    dcc.Loading(html.Div(id="fairness-analysis"), type="dot")
                ])
            ], className="shadow-sm h-100")
        ], width=6),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Data Drift Detection", className="fw-semibold"),
                dbc.CardBody([
                    dcc.Loading(html.Div(id="drift-analysis"), type="dot")
                ])
            ], className="shadow-sm h-100")
        ], width=6)
    ], className="mb-4 g-4"),
    
    dcc.Interval(
        id='interval-component',
        interval=60*1000,  # Update every minute
        n_intervals=0
    ),

    html.Footer(
        dbc.Container(
            dbc.Row(
                dbc.Col(
                    html.Small(
                        "© " + str(datetime.now().year) + " HealthFlow-MS — Modern UI", 
                        className="text-muted"
                    ), width=12
                )
            ), className="py-3"
        )
    )
], fluid=True)

# Callbacks
@app.callback(
    [Output('data-summary', 'children'),
     Output('performance-metrics', 'children'),
     Output('risk-distribution-chart', 'figure'),
     Output('temporal-trends-chart', 'figure'),
     Output('fairness-analysis', 'children'),
     Output('drift-analysis', 'children')],
    [Input('time-period-dropdown', 'value'),
     Input('interval-component', 'n_intervals')]
)
def update_dashboard(days_back, n_intervals):
    """Update all dashboard components"""
    try:
        # Fetch data
        df = analyzer.get_prediction_data(days_back)
        
        if df.empty:
            empty_fig = go.Figure()
            empty_fig.add_annotation(text="No data available", showarrow=False)
            
            return (
                dbc.Alert("No data available for the selected period", color="warning"),
                dbc.Alert("No performance metrics available", color="warning"),
                empty_fig,
                empty_fig,
                dbc.Alert("No fairness analysis available", color="warning"),
                dbc.Alert("No drift analysis available", color="warning")
            )
        
        # Data summary
        data_summary = dbc.ListGroup([
            dbc.ListGroupItem(f"Total Predictions: {len(df)}"),
            dbc.ListGroupItem(f"Unique Patients: {df['patient_pseudo_id'].nunique()}"),
            dbc.ListGroupItem(f"Date Range: {df['prediction_timestamp'].min().strftime('%Y-%m-%d')} to {df['prediction_timestamp'].max().strftime('%Y-%m-%d')}")
        ])
        
        # Performance metrics
        metrics = analyzer.calculate_model_performance_metrics(df)
        
        if metrics:
            performance_cards = dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(f"{metrics.get('mean_risk_score', 0):.3f}", className="card-title"),
                            html.P("Mean Risk Score", className="card-text")
                        ])
                    ])
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(f"{metrics.get('std_risk_score', 0):.3f}", className="card-title"),
                            html.P("Risk Score Std", className="card-text")
                        ])
                    ])
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(f"{metrics.get('total_predictions', 0)}", className="card-title"),
                            html.P("Total Predictions", className="card-text")
                        ])
                    ])
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H4(f"{metrics.get('mean_confidence', 0) or 0:.3f}", className="card-title"),
                            html.P("Mean Confidence", className="card-text")
                        ])
                    ])
                ], width=3)
            ])
        else:
            performance_cards = dbc.Alert("Performance metrics unavailable", color="warning")
        
        # Risk distribution chart
        risk_dist_fig = px.histogram(
            df, x='risk_score', nbins=20,
            title="Risk Score Distribution",
            labels={'risk_score': 'Risk Score', 'count': 'Frequency'}
        )
        risk_dist_fig.update_layout(showlegend=False)
        
        # Temporal trends chart
        daily_df = df.set_index('prediction_timestamp').resample('D')['risk_score'].agg(['count', 'mean'])
        temporal_fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=("Daily Prediction Count", "Daily Mean Risk Score"),
            vertical_spacing=0.1
        )
        
        temporal_fig.add_trace(
            go.Scatter(x=daily_df.index, y=daily_df['count'], name='Count'),
            row=1, col=1
        )
        temporal_fig.add_trace(
            go.Scatter(x=daily_df.index, y=daily_df['mean'], name='Mean Risk Score'),
            row=2, col=1
        )
        temporal_fig.update_layout(height=400, showlegend=False)
        
        # Fairness analysis
        features_df = analyzer.extract_features_from_data(df)
        fairness_results = analyzer.analyze_fairness_by_demographics(features_df)
        
        if fairness_results:
            fairness_content = []
            
            # Gender fairness
            if 'gender' in fairness_results:
                gender_df = pd.DataFrame(fairness_results['gender']).T
                fairness_content.append(html.H5("Gender Fairness"))
                fairness_content.append(
                    dash_table.DataTable(
                        data=gender_df.reset_index().to_dict('records'),
                        columns=[{"name": i, "id": i} for i in gender_df.reset_index().columns],
                        style_cell={'textAlign': 'left'}
                    )
                )
            
            # Disparate impact
            if 'disparate_impact' in fairness_results:
                di = fairness_results['disparate_impact']
                color = "success" if di['is_fair'] else "danger"
                fairness_content.append(html.Hr())
                fairness_content.append(
                    dbc.Alert([
                        html.H5("Disparate Impact Analysis"),
                        html.P(f"Disparate Impact Ratio: {di['disparate_impact_ratio']:.3f}"),
                        html.P(f"Fair Model: {'Yes' if di['is_fair'] else 'No'}")
                    ], color=color)
                )
            
            fairness_analysis = html.Div(fairness_content) if fairness_content else dbc.Alert("No fairness analysis available", color="info")
        else:
            fairness_analysis = dbc.Alert("Insufficient data for fairness analysis", color="info")
        
        # Drift analysis
        drift_results = analyzer.analyze_data_drift(features_df)
        
        if drift_results.get('status') == 'completed':
            drift_content = [
                html.H5("Data Drift Analysis"),
                dbc.ListGroup([
                    dbc.ListGroupItem(f"Dataset Drift Detected: {'Yes' if drift_results.get('dataset_drift_detected') else 'No'}"),
                    dbc.ListGroupItem(f"Drift Score: {drift_results.get('drift_score', 0):.3f}"),
                    dbc.ListGroupItem(f"Reference Period: {drift_results.get('reference_period')}"),
                    dbc.ListGroupItem(f"Current Period: {drift_results.get('current_period')}"),
                    dbc.ListGroupItem(f"Features Analyzed: {drift_results.get('features_analyzed')}")
                ])
            ]
            drift_analysis = html.Div(drift_content)
        else:
            drift_analysis = dbc.Alert(f"Drift analysis: {drift_results.get('status', 'Unknown status')}", color="info")
        
        return (
            data_summary,
            performance_cards,
            risk_dist_fig,
            temporal_fig,
            fairness_analysis,
            drift_analysis
        )
        
    except Exception as e:
        logger.error(f"Error updating dashboard: {e}")
        error_msg = dbc.Alert(f"Error updating dashboard: {str(e)}", color="danger")
        empty_fig = go.Figure()
        return error_msg, error_msg, empty_fig, empty_fig, error_msg, error_msg

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=False)