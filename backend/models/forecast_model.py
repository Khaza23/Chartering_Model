import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import date, timedelta
import warnings
warnings.filterwarnings("ignore")


@dataclass
class ForecastResult:
    forecast_value: float
    lower_bound: float
    upper_bound: float
    confidence: float
    forecast_date: date
    route: str
    vessel_class: str
    model_version: str = "ensemble_v1"


class FreightForecaster:
    def __init__(self):
        self.prophet_model = None
        self.xgboost_model = None
        self.prophet_weight = 0.4
        self.xgboost_weight = 0.6
        self.feature_columns = []

    def train(self, df: pd.DataFrame, route: str, vessel_class: str):
        route_df = df[(df["route"] == route) & (df["vessel_class"] == vessel_class)].copy()
        # Reconfigure: live feeds have weekend/holiday gaps (no Baltic assessment).
        # Keep a usable fallback instead of 500ing on sparse windows.
        if len(route_df) < 7:
            raise ValueError(f"Insufficient data for {route}/{vessel_class}: {len(route_df)} rows")
        if len(route_df) < 30:
            # Small-sample path: skip Prophet seasonality, rely on naive/XGBoost.
            route_df = route_df.sort_values("date").reset_index(drop=True)
            self.prophet_model = None
            self._train_xgboost(route_df)
            self.prophet_weight = 0.0
            self.xgboost_weight = 1.0 if self.xgboost_model is not None else 0.0
            return self

        route_df = route_df.sort_values("date").reset_index(drop=True)
        self._train_prophet(route_df)
        self._train_xgboost(route_df)

        if self.prophet_model is not None and self.xgboost_model is not None:
            self.prophet_weight = 0.4
            self.xgboost_weight = 0.6
        elif self.xgboost_model is not None:
            self.prophet_weight = 0.0
            self.xgboost_weight = 1.0
        elif self.prophet_model is not None:
            self.prophet_weight = 1.0
            self.xgboost_weight = 0.0
        else:
            self.prophet_weight = 0.5
            self.xgboost_weight = 0.5
        return self

    def _train_prophet(self, df: pd.DataFrame):
        try:
            from prophet import Prophet

            prophet_df = df[["date", "rate_usd_per_ton"]].rename(
                columns={"date": "ds", "rate_usd_per_ton": "y"}
            )
            prophet_df["ds"] = pd.to_datetime(prophet_df["ds"])

            self.prophet_model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                changepoint_prior_scale=0.05,
                seasonality_prior_scale=10,
                interval_width=0.82
            )
            self.prophet_model.fit(prophet_df)
        except Exception:
            self.prophet_model = None

    def _train_xgboost(self, df: pd.DataFrame):
        try:
            from xgboost import XGBRegressor
            from sklearn.model_selection import TimeSeriesSplit

            feature_cols = [c for c in df.columns if c not in [
                "date", "rate_usd_per_ton", "route", "vessel_class", "source"
            ]]

            numeric_cols = df[feature_cols].select_dtypes(include=[np.number]).columns.tolist()
            self.feature_columns = numeric_cols

            X = df[numeric_cols].fillna(0)
            y = df["rate_usd_per_ton"]

            self.xgboost_model = XGBRegressor(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                objective="reg:squarederror"
            )

            tscv = TimeSeriesSplit(n_splits=3)
            for train_idx, val_idx in tscv.split(X):
                X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
                self.xgboost_model.fit(
                    X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    verbose=False
                )

            self.xgboost_model.fit(X, y, verbose=False)

        except Exception:
            self.xgboost_model = None

    def predict(self, df: pd.DataFrame, forecast_days: int = 30,
                route: str = None, vessel_class: str = None) -> List[ForecastResult]:
        if df.empty:
            return []

        route_df = df.copy()
        if route:
            route_df = route_df[route_df["route"] == route]
        if vessel_class:
            route_df = route_df[route_df["vessel_class"] == vessel_class]

        if route_df.empty:
            return []

        route_df = route_df.sort_values("date").reset_index(drop=True)
        last_date = route_df["date"].max()
        last_row = route_df.iloc[-1]

        prophet_pred = self._predict_prophet(last_date, forecast_days)
        xgb_pred = self._predict_xgboost(route_df, forecast_days)

        results = []
        for i in range(forecast_days):
            forecast_date = last_date + timedelta(days=i + 1)

            if prophet_pred is not None and i < len(prophet_pred):
                p_val = prophet_pred.iloc[i]["yhat"]
                p_lower = prophet_pred.iloc[i]["yhat_lower"]
                p_upper = prophet_pred.iloc[i]["yhat_upper"]
            else:
                p_val = last_row["rate_usd_per_ton"]
                p_lower = p_val * 0.85
                p_upper = p_val * 1.15

            if xgb_pred is not None and i < len(xgb_pred):
                x_val = xgb_pred[i]
                x_std = route_df["rate_usd_per_ton"].std() * 0.15
                x_lower = x_val - 1.15 * x_std
                x_upper = x_val + 1.15 * x_std
            else:
                x_val = last_row["rate_usd_per_ton"]
                x_lower = x_val * 0.85
                x_upper = x_val * 1.15

            if self.prophet_model is not None and self.xgboost_model is not None:
                ensemble_val = self.prophet_weight * p_val + self.xgboost_weight * x_val
                ensemble_lower = self.prophet_weight * p_lower + self.xgboost_weight * x_lower
                ensemble_upper = self.prophet_weight * p_upper + self.xgboost_weight * x_upper
            elif self.xgboost_model is not None:
                ensemble_val = x_val
                ensemble_lower = x_lower
                ensemble_upper = x_upper
            elif self.prophet_model is not None:
                ensemble_val = p_val
                ensemble_lower = p_lower
                ensemble_upper = p_upper
            else:
                base = last_row["rate_usd_per_ton"]
                ensemble_val = base
                ensemble_lower = base * 0.85
                ensemble_upper = base * 1.15

            confidence = self._compute_confidence(route_df, float(ensemble_val))

            results.append(ForecastResult(
                forecast_value=float(round(float(ensemble_val), 2)),
                lower_bound=float(round(float(ensemble_lower), 2)),
                upper_bound=float(round(float(ensemble_upper), 2)),
                confidence=float(round(float(confidence), 2)),
                forecast_date=forecast_date.date() if hasattr(forecast_date, "date") else forecast_date,
                route=str(route or route_df["route"].iloc[0]),
                vessel_class=str(vessel_class or route_df["vessel_class"].iloc[0])
            ))

        return results

    def _predict_prophet(self, last_date, forecast_days):
        if self.prophet_model is None:
            return None

        try:
            future = self.prophet_model.make_future_dataframe(periods=forecast_days)
            forecast = self.prophet_model.predict(future)
            return forecast.tail(forecast_days)
        except Exception:
            return None

    def _predict_xgboost(self, df: pd.DataFrame, forecast_days: int):
        if self.xgboost_model is None or not self.feature_columns:
            return None

        try:
            predictions = []
            working_df = df.copy()

            for i in range(forecast_days):
                last_row = working_df.iloc[-1:]
                features = last_row[self.feature_columns].fillna(0)
                pred = float(self.xgboost_model.predict(features)[0])
                predictions.append(pred)

                new_row = last_row.copy()
                new_row["date"] = new_row["date"] + timedelta(days=1)
                new_row["rate_usd_per_ton"] = pred
                new_row["lag_1"] = pred
                if "rolling_mean_7" in new_row.columns:
                    recent = working_df["rate_usd_per_ton"].tail(6).tolist() + [pred]
                    new_row["rolling_mean_7"] = float(np.mean(recent))
                working_df = pd.concat([working_df, new_row], ignore_index=True)

            return predictions
        except Exception:
            return None

    def _compute_confidence(self, df: pd.DataFrame, forecast_val: float) -> float:
        recent = df["rate_usd_per_ton"].tail(30)
        if len(recent) < 7:
            return 0.5

        volatility = recent.std() / recent.mean()
        mean_val = recent.mean()
        deviation = abs(forecast_val - mean_val) / mean_val

        vol_score = max(0, 1 - volatility * 5)
        dev_score = max(0, 1 - deviation * 10)
        trend_score = 0.7 if abs(recent.pct_change(7).mean()) < 0.02 else 0.5

        confidence = 0.35 * vol_score + 0.35 * dev_score + 0.30 * trend_score
        return max(0.3, min(0.95, confidence))

    def backtest(self, df: pd.DataFrame, route: str, vessel_class: str,
                 test_months: int = 6) -> Dict:
        route_df = df[(df["route"] == route) & (df["vessel_class"] == vessel_class)].copy()
        route_df = route_df.sort_values("date").reset_index(drop=True)

        if len(route_df) < test_months * 30 + 60:
            return {"error": "Insufficient data for backtesting"}

        split_date = route_df["date"].max() - timedelta(days=test_months * 30)
        train_df = route_df[route_df["date"] <= split_date].copy()
        test_df = route_df[route_df["date"] > split_date].copy()

        self.train(train_df, route, vessel_class)

        naive_pred = train_df["rate_usd_per_ton"].iloc[-1]
        ma_30 = train_df["rate_usd_per_ton"].tail(30).mean()

        actuals = test_df["rate_usd_per_ton"].values
        naive_errors = []
        ma_errors = []
        prophet_errors = []
        xgb_errors = []
        ensemble_errors = []

        for idx, row in test_df.iterrows():
            actual = row["rate_usd_per_ton"]

            naive_errors.append(abs(naive_pred - actual))
            ma_errors.append(abs(ma_30 - actual))

            sub_train = route_df[route_df["date"] <= row["date"]]
            if len(sub_train) >= 30:
                try:
                    temp_forecaster = FreightForecaster()
                    temp_forecaster.train(sub_train, route, vessel_class)
                    preds = temp_forecaster.predict(sub_train, forecast_days=1,
                                                    route=route, vessel_class=vessel_class)
                    if preds:
                        ensemble_errors.append(abs(preds[0].forecast_value - actual))
                except Exception:
                    pass

        metrics = {
            "mae_naive": np.mean(naive_errors) if naive_errors else None,
            "mae_ma30": np.mean(ma_errors) if ma_errors else None,
            "mae_ensemble": np.mean(ensemble_errors) if ensemble_errors else None,
            "rmse_naive": np.sqrt(np.mean(np.array(naive_errors) ** 2)) if naive_errors else None,
            "rmse_ensemble": np.sqrt(np.mean(np.array(ensemble_errors) ** 2)) if ensemble_errors else None,
            "directional_accuracy": self._directional_accuracy(actuals) if len(actuals) > 1 else None,
            "test_points": len(actuals),
            "train_points": len(train_df)
        }

        return metrics

    def _directional_accuracy(self, actuals) -> float:
        if len(actuals) < 2:
            return 0.0
        changes = np.diff(actuals)
        predicted_direction = np.sign(changes[:-1])
        actual_direction = np.sign(changes[1:])
        return float(np.mean(predicted_direction == actual_direction))
