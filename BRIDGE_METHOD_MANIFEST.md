# Your Company Virtual Office — Bridge Method Manifest

**Build:** v3.2.7  |  **Total methods:** 473

Canonical entry points for the most common workflows. Use these
exact names from chat or scripts. Many natural-language phrases
also route here (see the chat interceptor list in `app.js`).

---

## STATUS / DASHBOARD

| Method | Signature | Purpose |
|---|---|---|
| `daily_status` | `() -> 'dict'` | One-line top-of-day status. the Owner's quickest glance. |
| `get_kpis` | `() -> 'dict'` | Return real KPI data from the bid pipeline database. |
| `get_health` | `() -> 'dict'` | (no docstring) |
| `morning_briefing` | `() -> 'dict'` | Local 'what to look at today' summary. No LLM required. |
| `get_pipeline_summary` | `() -> 'dict'` | Kanban-style bid pipeline summary. |
| `get_steel_brief_context` | `() -> 'dict'` | Get context data for generating the weekly Steel Intelligence Brief. |

## BIDS

| Method | Signature | Purpose |
|---|---|---|
| `list_bids` | `(status: 'str' = '', limit: 'int' = 20) -> 'dict'` | List bids from the pipeline. |
| `add_bid` | `(proposal_no: 'str', project_name: 'str', gc_name: 'str' = '', city: 'str' = 'HOU', base_bid_total: 'float' = 0, deadline: 'str' = '', drawing_stage: 'str' = 'IFC') -> 'dict'` | Add a new bid to the pipeline. |
| `update_bid_status` | `(proposal_no: 'str', status: 'str', notes: 'str' = '') -> 'dict'` | Update bid status in the pipeline. |
| `get_bid_template` | `(template_name: 'str' = 'STANDARD') -> 'dict'` | Get bid output template definition. |
| `set_bid_template` | `(template_name: 'str' = 'STANDARD') -> 'dict'` | Set the active bid output template. |
| `get_bid_detail` | `(bid_id: 'int') -> 'dict'` | (no docstring) |
| `get_bid_leads` | `(tier: 'str' = '', limit: 'int' = 10) -> 'dict'` | Get recommended bid leads from the database. |
| `check_bid_emr` | `(emr, prospect_type: 'str' = 'standard_gc') -> 'dict'` | Check EMR eligibility for a bid. v3.2.7: coerce emr to float. |
| `check_bid_compliance` | `(content: 'str' = '', context: 'str' = 'bid') -> 'dict'` | Check content against Tier 1 compliance rules. |
| `next_bid_number` | `(city: 'str' = 'HOU') -> 'dict'` | Generate the next sequential proposal number. |
| `compose_full_bid` | `(bid_text: 'str' = '', pdf_path: 'str' = '', project_name: 'str' = '', gc_company: 'str' = '') -> 'dict'` | THE CROWN JEWEL: Full autonomous bid composition. |
| `generate_proposal_from_bid` | `(bid_id: 'int' = 0, project_name: 'str' = '', total_bid: 'float' = 0, tonnage: 'float' = 0, building_sf: 'float' = 0, gc_name: 'str' = '', gc_company: 'str' = '', terms: 'str' = 'Net 30', notes: 'str' = '') -> 'dict'` | One-call proposal PDF from a pipeline-DB bid_id, OR from explicit fields. |

## COMPLIANCE

| Method | Signature | Purpose |
|---|---|---|
| `compliance_summary` | `() -> 'dict'` | One-line summary of compliance state. the Owner's glance command. |
| `get_compliance` | `() -> 'dict'` | (no docstring) |
| `get_compliance_stats` | `() -> 'dict'` | Compliance agent statistics. |
| `check_bid_emr` | `(emr, prospect_type: 'str' = 'standard_gc') -> 'dict'` | Check EMR eligibility for a bid. v3.2.7: coerce emr to float. |
| `get_isn_scorecard` | `() -> 'dict'` | ISNetworld scorecard polling + document-expiry alerts. |
| `cascade_compliance` | `(item_n: 'int' = 0, new_status: 'str' = 'OPEN', note: 'str' = '') -> 'dict'` | Apply a cascade hint: advance a dependent BLOCKED item now that its |
| `set_compliance_status` | `(item_n: 'int' = 0, status: 'str' = '', note: 'str' = '') -> 'dict'` | Directly set any compliance item's status from chat. No dependency |

## AISC / STEEL

| Method | Signature | Purpose |
|---|---|---|
| `get_aisc_member_info` | `(designation: 'str' = '') -> 'dict'` | Look up a single AISC shape in the local CSV database. |
| `normalize_shape` | `(raw_shape: 'str' = '', pe_firm: 'str' = '') -> 'dict'` | Normalize a shape using firm-specific rules first, |
| `list_steel_shapes` | `() -> 'dict'` | List all available AISC shapes in the local database. |
| `aisc_mass_balance` | `(extracted_tonnage: 'float' = 0, members: 'str' = '[]') -> 'dict'` | Compare AI-extracted tonnage vs member-calculated tonnage. |
| `calculate_plate_weight` | `(notation: 'str' = '', qty: 'int' = 1, thickness_in: 'float' = 0, width_in: 'float' = 0, length_in: 'float' = 0) -> 'dict'` | Calculate weight of steel plates (not in AISC database). |
| `get_latest_steel_prices` | `() -> 'dict'` | Latest price from every source (FRED, CME, AISI, service-center). |
| `get_steel_research` | `() -> 'dict'` | Get steel market intelligence from free sources. |

## 3D / TAKEOFF

| Method | Signature | Purpose |
|---|---|---|
| `generate_3d_view` | `(shape: 'str' = 'W14X82', length_ft: 'float' = 20, count: 'int' = 1) -> 'dict'` | Generate a 3D STL model from AISC shape data - 100% local calculation. |
| `generate_3d_model` | `(members_json: 'str') -> 'dict'` | Generate 3D STL model from a JSON list of members. |
| `run_hybrid_3d_pipeline` | `(pdf_path: 'str' = '') -> 'dict'` | Full hybrid pipeline: PDF drawing → AI vision → AISC match → 3D model → cost est |
| `auto_process_drawing` | `(pdf_path: 'str', bid_number: 'str' = '', project_name: 'str' = '', allow_local_short_circuit: 'bool' = True, force_new: 'bool' = False) -> 'dict'` | Auto-pipeline triggered when a structural drawing PDF is uploaded. |
| `start_auto_process_drawing` | `(pdf_path: 'str', drawing_stage: 'str' = '', expected_tonnage: 'str' = '', use_cache: 'bool' = True, force_new_bid: 'bool' = False) -> 'dict'` | Background variant of auto_process_drawing. |
| `poll_auto_process_drawing` | `(job_id: 'str') -> 'dict'` | Poll a background auto_process_drawing job. |
| `takeoff_from_pdf` | `(pdf_path: 'str', project_name: 'str' = '') -> 'dict'` | AI plan reader - PDF → classified sheets → detected members → BOM. |
| `detect_misc_steel` | `(pdf_path: 'str' = '', text: 'str' = '', page_num: 'int' = 0) -> 'dict'` | Detect misc steel from a PDF or raw text. |
| `estimate_misc_steel` | `(verified_tons: 'float' = 0, member_count: 'int' = 0, building_type: 'str' = 'commercial', plates_json: 'str' = '') -> 'dict'` | Estimate misc steel (connections, plates, hardware) as % of tonnage. |

## EXPORTS / FINANCE

| Method | Signature | Purpose |
|---|---|---|
| `export_tekla_xml` | `(bid_number: 'str' = '', project_name: 'str' = '', members_json: 'str' = '') -> 'dict'` | Export takeoff data as Tekla PowerFab XML. |
| `export_strumis_xml` | `(bid_number: 'str' = '', project_name: 'str' = '', members_json: 'str' = '') -> 'dict'` | Export takeoff data as Strumis ERP XML. |
| `get_markup_margin_table` | `() -> 'dict'` | Markup vs margin conversion table (always show both per handoff doc). |
| `get_lien_calendar` | `(project_start: 'str', role: 'str' = 'original_contractor') -> 'dict'` | Texas Property Code Ch. 53 lien-notice calendar. Non-negotiable deadlines. |
| `generate_pay_app` | `(project_name: 'str', contractor: 'str', owner: 'str', architect: 'str', app_number: 'int', period_to: 'str', sov_items: 'list', retainage_pct: 'float' = 10) -> 'dict'` | Generate AIA G702/G703 pay application PDF. |
| `export_project_card_pdf` | `(project_data: 'dict' = None) -> 'dict'` | Export the project card to a Your Company branded PDF. |
| `check_schedule_feasibility` | `(tons: 'float', ship_date: 'str') -> 'dict'` | Check if shop capacity can meet the ship date. |
| `get_fab_productivity` | `(hours: 'float', tons: 'float', complexity: 'str' = 'medium') -> 'dict'` | Compare fabrication productivity to industry benchmarks. |

## EMAIL / GMAIL

| Method | Signature | Purpose |
|---|---|---|
| `scan_recent_gmail_for_engagements` | `(days_back: 'int' = 1, max_messages: 'int' = 50, dry_run: 'bool' = True) -> 'dict'` | Pull recent Gmail messages via MCP and propose engagement records. |
| `mail_scanner_status` | `() -> 'dict'` | Get M365 mail scanner status (configured, running, mailbox). |

## VJ (SELF-REPAIR)

| Method | Signature | Purpose |
|---|---|---|
| `vj_scan` | `() -> 'dict'` | Virtual Joseph: scan the entire codebase for bugs, gaps, and issues. |
| `vj_scan_and_fix` | `(fast_mode: 'bool' = False) -> 'dict'` | Virtual Joseph: scan the codebase AND auto-fix what can be fixed. |
| `vj_route` | `(request: 'str' = '') -> 'dict'` | Route a request to the best tool and AI model. |
| `vj_train` | `(export_path: 'str' = '') -> 'dict'` | Train Virtual Joseph from a Claude data export. |
| `vj_check_deps` | `() -> 'dict'` | Check all project dependencies and return install guide for missing ones. |
| `vj_check_bias` | `(text: 'str' = '') -> 'dict'` | Check text for AI-model bias patterns before sending. |
| `vj_validate` | `(request: 'str' = '', response: 'str' = '') -> 'dict'` | Validate a response before delivery using Virtual Joseph. |
| `vj_designed_features` | `() -> 'dict'` | List all features VJ has designed. |
| `vj_routing_stats` | `() -> 'dict'` | Get routing statistics. |

## PROJECT CONTROLS (PC4+PC5, internal only)

| Method | Signature | Purpose |
|---|---|---|
| `get_spi_cpi` | `(project_id: 'str' = '') -> 'dict'` | SPI/CPI per WBS line plus S-curve series; flag below 0.95 either index. CONFIDENTIAL - INTERNAL. |
| `get_forecast_to_complete` | `(project_id: 'str' = '') -> 'dict'` | EAC/ETC per line rolled to project; Section 07 control limits -1.7/+7.3 percent. CONFIDENTIAL - INTERNAL. |
| `get_variance_by_cost_code` | `(project_id: 'str' = '') -> 'dict'` | Cost and schedule variance by cost code; client-caused lines carry the notice note (PC6). CONFIDENTIAL - INTERNAL. |

## OTHER BRIDGE METHODS (414 ungrouped)

Available but not yet categorized:

  `activate_api`  `add_blocker`  `add_certificate`  `add_contact`
  `add_cost_entry`  `add_project`  `add_shop_piece`  `add_to_hash_chain`
  `add_to_pipeline`  `add_welder`  `advance_bid`  `advance_co_status`
  `ai_ask`  `analyze_bid`  `analyze_connection_details`  `analyze_spec`
  `audit_spec_book`  `auto_process_project_files`  `auto_respond_to_bid`  `backtest_project`
  `batch_check_connections`  `bid_history_compare`  `bid_history_log`  `build_full_building`
  `calc_weld_consumable`  `calculate_emr`  `calculate_emr_2025`  `calculate_freight`
  `calculate_lien_deadlines`  `capacity_adjusted_margin`  `capture_drone`  `check_bc_status`
  `check_bond_capacity`  `check_connections`  `check_davis_bacon`  `check_engagement_record`
  `check_expiring_certs`  `check_osha`  `check_si_required`  `check_voice`
  `check_welder_drift`  `check_wps_d11_2025`  `classify_intent`  `classify_shop_drawing_review`
  `clear_vision_cache`  `compare_actuals`  `compare_drawing_revisions`  `compare_grades`
  `compliance_diff`  `compliance_snapshot`  `compute_assembly_costs`  `configure_watchdog`
  `confirm_imessage_send`  `confirm_refinery_outreach`  `create_ar_milestones`  `create_bluebeam_session`
  `create_co`  `create_engagement_record`  `create_rfi`  `cross_verify`
  `deactivate_api`  `design_base_plate`  `design_shear_tab`  `detect_welder_drift`
  `diff_addendum`  `draft_email_outlook`  `draft_refinery_outreach`  `drawing_revision_diff`
  `emit_event`  `estimate_connection_weight`  `estimate_project_consumables`  `estimate_weld_consumable`
  `execute_objective`  `export_all_data`  `export_misc_steel_to_tekla`  `extract_cad_layer`
  `extract_drawing_set`  `extract_submittals`  `factory_reset`  `feature_status`
  `fetch_price_emails`  `fetch_steel_prices`  `fred_key_status`  `gdrive_pull`
  `gdrive_push`  `gdrive_sync_status`  `generate_calc_pack`  `generate_case_study`
  `generate_change_order`  `generate_dstv`  `generate_dxf`  `generate_followup_sequence`
  `generate_gcode`  `generate_gp_only`  `generate_ironworker`  `generate_part_dxf`
  `generate_piece_qr`  `generate_proposal`  `generate_punch_map`  `generate_rfi_log`
  `generate_scope_narrative`  `generate_stl`  `generate_stop_list`  `generate_wireframe`
  `get_agent_health`  `get_api_capabilities`  `get_api_registry`  `get_app_info`
  `get_ar_aging`  `get_ar_alerts`  `get_ar_status`  `get_audit_log`
  `get_audit_readiness`  `get_auto_defaults`  `get_best_steel_price`  `get_bid_pipeline`
  `get_bid_rates`  `get_bids_folder`  `get_blockers`  `get_bom`
  `get_bond_capacity`  `get_calibrated_estimate`  `get_calibration_summary`  `get_cash_flow_projection`
  `get_ceo_log`  `get_chain_capability`  `get_change_orders`  `get_channel_config`
  `get_claude_app_config`  `get_claude_app_setup`  `get_connection_cost`  `get_contact`
  `get_contacts_for_email`  `get_conversation_history`  `get_correction_summary`  `get_cost_engine_status`
  `get_data_feed_stats`  `get_davis_bacon_rates`  `get_disa_status`  `get_display_prefs`
  `get_dual_account_strategy`  `get_due_followups`  `get_escalation_threshold`  `get_event_log`
  `get_federal_opportunities`  `get_field_vision_stats`  `get_financial_dashboard`  `get_fuel_surcharge`
  `get_governance_audit`  `get_governance_resolution`  `get_governance_status`  `get_graph_runner_status`
  `get_hedge_recommendation`  `get_hedged_cost`  `get_houston_briefing`  `get_houston_news`
  `get_houston_pipeline`  `get_integration_credentials`  `get_integrations`  `get_iot_dashboard`
  `get_job_production_status`  `get_landed_cost`  `get_last_session`  `get_learning_status`
  `get_ledger_stats`  `get_lien_deadlines`  `get_macro_indicators`  `get_market_dashboard`
  `get_memory_status`  `get_message_log`  `get_morning_brief`  `get_nesting_solution`
  `get_news_digest`  `get_openhuman_recent_files`  `get_openhuman_status`  `get_osha_300a`
  `get_outreach_log`  `get_overrun_risk`  `get_panel_data`  `get_pdf_qc_rules`
  `get_permit_fee`  `get_pipeline`  `get_pipeline_progress`  `get_pipeline_stats`
  `get_portfolio_brief`  `get_prequal_status`  `get_prequalified_wps`  `get_priorities`
  `get_production_board`  `get_productivity_kpis`  `get_project_costs`  `get_project_pipeline`
  `get_project_profit`  `get_projects`  `get_qb_coa_mapping`  `get_qbo_sync`
  `get_quick_actions`  `get_rate_history`  `get_rates`  `get_ravs_scorecard`
  `get_reminders`  `get_resilience_status`  `get_revenue_attribution`  `get_rfis`
  `get_rules`  `get_sentry_release`  `get_session_state`  `get_shop_iot`
  `get_shop_kpis`  `get_shop_log`  `get_sms_event_toggles`  `get_sms_status`
  `get_special_inspectors`  `get_standing_files`  `get_steel_agent_stats`  `get_steel_price`
  `get_steel_prices`  `get_stock_brief`  `get_system_inventory`  `get_team`
  `get_tekla_data`  `get_time_saved`  `get_token_routing`  `get_token_usage`
  `get_turnaround_calendar`  `get_user_pref`  `get_valid_shapes`  `get_vault_sync_status`
  `get_vision_tier_status`  `get_wage_rate`  `get_watchdog_status`  `get_wc_rate`
  `get_welder_alerts`  `get_win_probability`  `get_workbench_data`  `get_wps_status`
  `ghost_overlay`  `hash_drawing_pages`  `import_accounting_csv`  `import_from_backup`
  `import_qb_trial_balance`  `import_qb_trial_balance_file`  `index_project`  `ingest_service_center_prices`
  `inspect_weld_image`  `inspect_weld_vision`  `integrate_api`  `kill_all_stale_bids`
  `kill_bid`  `knowledge_for_ai`  `knowledge_query`  `link_spec_clauses`
  `list_active_bids`  `list_bid_artifacts`  `list_engagement_records`  `list_fab_tools`
  `list_intents`  `list_recent_bids`  `list_skills`  `load_skill`
  `log_ar_payment`  `log_drone_flight`  `log_production`  `log_project_completion`
  `log_sensor_reading`  `log_shop_activity`  `log_weld_inspection`  `mark_bid_lost`
  `mark_bid_won`  `mark_lead_actioned`  `match_opportunity`  `match_skill`
  `mcp_call_tool`  `mcp_list_servers`  `mcp_list_tools`  `mcp_prefer_routing`
  `mcp_status`  `nest_shapes`  `open_bids_folder`  `optimize_crew`
  `optimize_cut_list`  `orchestration_ingest`  `orchestration_proofread`  `orchestration_status`
  `orchestration_verify`  `parse_dstv`  `parse_dstv_extended`  `parse_ifc`
  `parse_price_sheet`  `parse_spec`  `parse_ssp_export`  `pipeline_score`
  `pipeline_summary_by_score`  `plan_building`  `plan_objective`  `plan_truck_loads`
  `poll_bid_invites`  `pre_dispatch_check`  `predict_bid_win`  `predict_emr`
  `predict_win_probability`  `preview_proposal_from_bid`  `process_drone_images`  `process_full_takeoff`
  `process_full_takeoff_v2`  `propose_engagement_from_email`  `prune_conversation_history`  `publish_mes_event`
  `pull_houston_pipeline`  `pull_rss_news`  `pull_steel_prices`  `quick_bid_estimate`
  `rasterize_drawing_page`  `read_bid_stl`  `read_bid_takeoff`  `recommend_erection_order`
  `recommend_hedge`  `record_shape_correction`  `record_weld_activity`  `register_openhuman_skill`
  `reload_compliance_state`  `remove_api`  `render_tagged_pdf`  `rescore_all_bids`
  `reset_vision_tier_tracker`  `resolve_blocker`  `restore_bid`  `review_bid_ssp`
  `route_vision_task`  `run_bid_chain`  `run_bid_harness`  `run_compliance_attacks`
  `run_compliance_check`  `run_daily_agents`  `run_diagnostics`  `run_learning_cycle`
  `run_monte_carlo`  `run_pdf_qc`  `run_self_test`  `run_self_test_suite`
  `run_takeoff`  `run_value_engineering`  `save_bid_artifact`  `save_channel_config`
  `save_integration_credentials`  `save_qb_mapping_override`  `save_temp_file`  `save_workbench_correction`
  `scan_bids`  `scan_engagements_from_messages`  `scan_piece`  `score_bid`
  `score_email_text`  `score_opportunity`  `search_contacts`  `search_conversations`
  `search_federal_opportunities`  `search_inbox_for_bid`  `search_openhuman_memory`  `search_project_memory`
  `send_email_outlook`  `send_imessage_to_contact`  `send_morning_briefing_now`  `send_sms_to_owner`
  `send_test_notification`  `session_boot`  `session_clear`  `session_set_takeoff`
  `session_status`  `set_ceo_preference`  `set_display_prefs`  `set_escalation_threshold`
  `set_sms_event_toggle`  `set_user_pref`  `setup_sms`  `shutdown`
  `start_tunnel`  `start_watchdog`  `start_webhook`  `stop_watchdog`
  `suggest_bid_number`  `test_connection`  `text_joseph_imessage`  `text_owner_imessage`
  `track_time_saved`  `update_bid_from_drawing`  `update_bid_rates`  `update_contact`
  `update_piece_status`  `update_project_costs`  `validate_shapes`  `validate_wage_rate`
  `vault_sync_preferences`  `vault_sync_projects`  `vault_sync_session`  `ve_suggestions`
  `verify_connection_fea`  `verify_document`  `verify_hash_chain`  `verify_photo_qc`
  `verify_tx_wc`  `version`  `vj_catalog_correction`  `vj_design_feature`
  `vj_get_corrections`  `vj_pick_ai`  `vj_sweep`  `vm_discover_bids`
  `vm_discovery_cards`  `vm_evaluate`  `vm_extract_links`  `vm_load_training`
  `vm_start_estimating`  `watchdog_poll_now`
