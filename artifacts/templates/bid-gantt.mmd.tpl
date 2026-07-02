%%{init: {'theme':'dark', 'themeVariables': {'fontFamily':'Segoe UI'}}}%%
gantt
    title {{bid_name}} - Bid Schedule
    dateFormat YYYY-MM-DD
    axisFormat %b %d

    section Engineering and Detailing
    Connection design        :crit, eng1, {{start_date}}, {{eng_days}}d
    Shop drawings            :eng2, after eng1, {{shop_dwg_days}}d
    Approval cycle           :eng3, after eng2, 10d

    section Procurement
    Mill order placed        :crit, proc1, after eng2, 1d
    Mill delivery            :proc2, after proc1, {{mill_lead_days}}d
    Deck order               :proc3, after eng2, 1d
    Deck delivery            :proc4, after proc3, {{deck_lead_days}}d
    Anchor bolts             :proc5, after eng2, 1d

    section Fabrication
    Shop fab start           :crit, fab1, after proc2, 1d
    Shop fab complete        :fab2, after fab1, {{fab_days}}d
    Galv if required         :fab3, after fab2, 7d
    Shop primer              :fab4, after fab2, 5d
    Ready to ship            :milestone, after fab4, 0d

    section Delivery and Erection
    Site mobilization        :crit, erect1, after fab4, 3d
    Steel erection           :erect2, after erect1, {{erect_days}}d
    Deck install             :erect3, after erect2, {{deck_install_days}}d
    Stud welding             :erect4, after erect3, {{stud_days}}d
    Punch and turnover       :erect5, after erect4, 5d
    Substantial completion   :milestone, after erect5, 0d
