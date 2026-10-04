"""Pandas groups our sales; Plotly draws the interactive chart."""
import pandas as pd
import plotly.graph_objects as go


def summarize(db, start, end):
    frame = pd.read_sql_query('''SELECT s.*, p.name, p.category FROM sales s
        JOIN products p ON p.sku=s.sku WHERE sold_on BETWEEN ? AND ?
        ORDER BY sold_on DESC, id DESC''', db, params=(start, end))
    frame['revenue'] = frame['quantity'] * frame['price_cents']
    frame['profit'] = frame['quantity'] * (frame['price_cents'] - frame['cost_cents'])
    revenue = int(frame['revenue'].sum())
    profit = int(frame['profit'].sum())
    metrics = dict(revenue=revenue, profit=profit, units=int(frame['quantity'].sum()),
                   transactions=len(frame), margin=round(profit / revenue * 100, 1) if revenue else 0)
    daily = frame.groupby('sold_on')[['revenue', 'profit']].sum()
    days = pd.date_range(start, end).strftime('%Y-%m-%d')
    daily = daily.reindex(days, fill_value=0)
    fig = go.Figure()
    for column, label, color in [('revenue', 'Revenue', '#4f63e6'), ('profit', 'Gross profit', '#22a18a')]:
        fig.add_trace(go.Scatter(x=list(daily.index), y=(daily[column] / 100).tolist(),
                                name=label, mode='lines', line=dict(color=color, width=3),
                                fill='tozeroy' if column == 'revenue' else None,
                                fillcolor='rgba(79,99,230,0.055)',
                                hovertemplate='%{x}<br>$%{y:,.2f}<extra>' + label + '</extra>'))
    fig.update_layout(template='plotly_white', height=290, margin=dict(l=45,r=15,t=15,b=35),
                      font=dict(family='Arial', color='#758096', size=11),
                      legend=dict(orientation='h', y=1.16, x=0),
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      hovermode='x unified', yaxis=dict(tickprefix='$', gridcolor='#eef1f6'),
                      xaxis=dict(showgrid=False), dragmode=False)
    chart = fig.to_html(full_html=False, include_plotlyjs=False,
                        config={'displayModeBar': False, 'responsive': True})
    top = frame.groupby(['sku','name'], as_index=False).agg(
        revenue=('revenue','sum'), profit=('profit','sum'), quantity=('quantity','sum'))
    top = top.sort_values('revenue', ascending=False).head(5).to_dict('records')
    largest = max([p['revenue'] for p in top], default=1) or 1
    for product in top:
        product['bar'] = round(product['revenue'] / largest * 100)
    return metrics, chart, top, frame.to_dict('records')
