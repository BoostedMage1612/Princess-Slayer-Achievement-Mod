# STP Achievement Guide -- owned file, version 0.2.3
# Guidance only. Game actions remain under the player's control.
init 990 python in stpguide:
    from store import renpy, config, achievement
    import store
    from stp_guide.controller import Guide
    guide = Guide(renpy, store, config, achievement)
    config.menu_arguments_callback = guide.menu_callback
    config.label_callback = guide.label_callback
    config.after_load_callbacks.append(guide.after_load)
    if 'stpg_overlay' not in config.always_shown_screens:
        config.always_shown_screens.append('stpg_overlay')

# Only these guide variables are changed. They follow Ren'Py saves and rollback.
default stpg_route_id = None
default stpg_cursor = 0
default stpg_paused = False
default stpg_hud = True

style stpg_text is default:
    font 'DejaVuSans.ttf'
    size 22
    color '#e8e1d5'
style stpg_button is button:
    background Solid('#272b34')
    hover_background Solid('#414653')
    padding (16, 12)
style stpg_button_text is stpg_text:
    hover_color '#ffe2a5'
    insensitive_color '#777b83'
style stpg_gold_button is stpg_button:
    background Solid('#574624')
    hover_background Solid('#796035')
style stpg_gold_button_text is stpg_button_text:
    color '#ffe2a5'
style stpg_frame is frame:
    background Solid('#13161cf5')
    padding (28, 24)

screen stpg_overlay():
    zorder 180
    key 'K_F8' action Function(stpguide.guide.open)
    key 'K_F10' action ToggleVariable('stpg_hud')
    if stpg_hud and stpg_route_id and not main_menu and not renpy.get_screen('stpg_panel'):
        frame:
            style 'stpg_frame'
            xpos 24
            ypos 28
            xmaximum 1100
            vbox:
                spacing 6
                text 'ACHIEVEMENT GUIDE  /  F8 panel  /  F10 hide' style 'stpg_text' size 17 color '#ddbb76'
                text stpguide.guide.message style 'stpg_text' size 20 substitute False
                if stpguide.guide.next_text:
                    text ('Next: '+stpguide.guide.next_text) style 'stpg_text' size 20 color '#ffe2a5' substitute False

screen stpg_panel():
    modal True
    zorder 240
    default selected = None
    default view = 'runs'
    key 'K_F8' action Hide('stpg_panel')
    key 'K_ESCAPE' action Hide('stpg_panel')
    add Solid('#000000b8')
    frame:
        style 'stpg_frame'
        align (0.5, 0.5)
        xsize 1760
        ysize 980
        vbox:
            spacing 16
            hbox:
                xfill True
                text 'ACHIEVEMENT GUIDE  v0.2.3' style 'stpg_text' size 36 color '#ffe2a5' xsize 1280
                textbutton 'Refresh' style 'stpg_button' action Function(stpguide.guide.refresh)
                textbutton 'Close' style 'stpg_button' action Hide('stpg_panel')
            if stpguide.guide.error:
                text stpguide.guide.error style 'stpg_text' color '#ffad9e'
            else:
                text ('Steam: %d / %d earned  |  %d missing  |  %d unknown    Gallery: %d / %d' % (len(stpguide.guide.earned), len(stpguide.guide.catalog), len(stpguide.guide.catalog)-len(stpguide.guide.earned)-len(stpguide.guide.unknown), len(stpguide.guide.unknown), len(stpguide.guide.gallery_earned), len(stpguide.guide.gallery_flags))) style 'stpg_text'
                if stpguide.guide.unknown:
                    text 'Steam has not confirmed every achievement. Unknown entries stay in the plan; launch through Steam and refresh.' style 'stpg_text' size 18 color '#ddbb76'
                if stpguide.guide.extra_ids:
                    text 'Steam lists new achievements outside this version of the guide. This build cannot claim complete coverage.' style 'stpg_text' size 18 color '#ffad9e'
                hbox:
                    spacing 12
                    textbutton 'Recommended runs' style 'stpg_button' action [SetScreenVariable('view','runs'),SetScreenVariable('selected',None)]
                    textbutton 'Missing achievements' style 'stpg_button' action [SetScreenVariable('view','achievements'),SetScreenVariable('selected',None)]
                    textbutton 'Missing gallery scenes' style 'stpg_button' action [SetScreenVariable('view','gallery'),SetScreenVariable('selected',None)]
                    textbutton ('Resume guide' if stpg_paused else 'Pause guide') style 'stpg_button' action Function(stpguide.guide.toggle_pause)
                hbox:
                    spacing 28
                    viewport:
                        xsize 930
                        ysize 678
                        mousewheel True
                        scrollbars 'vertical'
                        draggable True
                        vbox:
                            spacing 10
                            if view == 'runs':
                                text 'Ordered by new achievements, then gallery scenes. Counts below exclude rewards assigned to earlier runs.' style 'stpg_text' size 18 color '#b3b9c4' xmaximum 870
                                for pos, row in enumerate(stpguide.guide.ranked):
                                    textbutton ('%d.  %s\n%d new achievements · %d gallery flags · %d choices' % (pos+1, row['route']['name'], row['ach'], row['gallery'], len(row['route']['steps']))) style 'stpg_button' xsize 870 action SetScreenVariable('selected',row['route']['id'])
                                if not stpguide.guide.ranked:
                                    text 'No remaining mapped rewards.' style 'stpg_text'
                            elif view == 'achievements':
                                for entry in stpguide.guide.rows:
                                    if entry['status'] != 'earned':
                                        if entry['id'] == 'ACH_GALLERY_FIXED':
                                            textbutton (entry['title']+'\nComplete every gallery chapter and image.') style 'stpg_button' xsize 870 action SetScreenVariable('view','gallery')
                                        elif stpguide.guide.plans_for(entry['id']):
                                            $ best = stpguide.guide.plans_for(entry['id'])[0]
                                            textbutton (entry['title']+'\n'+entry['description']) style 'stpg_button' xsize 870 action SetScreenVariable('selected',best['id'])
                                        else:
                                            text (entry['title']+' — no validated route in this build') style 'stpg_text' color '#ffad9e'
                            else:
                                text 'These flags are required for “A Song to Remember”. The game records them when you reach the scene.' style 'stpg_text' size 18 xmaximum 870
                                if len(stpguide.guide.gallery_earned) == len(stpguide.guide.gallery_flags):
                                    text 'Every gallery flag is set. If Steam still lists the achievement as missing, use the recommended run to reach a gallery scene and let the game check it again.' style 'stpg_text' xmaximum 870
                                for goal in sorted(set(stpguide.guide.gallery_flags)-stpguide.guide.gallery_earned):
                                    if stpguide.guide.plans_for(goal):
                                        $ best = stpguide.guide.plans_for(goal)[0]
                                        textbutton stpguide.guide.title(goal) style 'stpg_button' xsize 870 action SetScreenVariable('selected',best['id'])
                                    else:
                                        text (stpguide.guide.title(goal)+' — route not mapped') style 'stpg_text' color '#ffad9e'
                    vbox:
                        xsize 700
                        spacing 14
                        if selected:
                            $ route = stpguide.guide.by_id[selected]
                            $ gains = stpguide.guide.score_now(route)
                            text route['name'] style 'stpg_text' size 29 color '#ffe2a5'
                            text ('From a new game: %d remaining achievements and %d gallery flags across %d choices.' % (gains[0], gains[1], len(route['steps']))) style 'stpg_text'
                            textbutton 'Start this guided run' style 'stpg_gold_button' action Function(stpguide.guide.start_new, selected)
                            if stpguide.guide.can_join(selected):
                                textbutton 'Join at the current choice' style 'stpg_button' action [Function(stpguide.guide.join, selected), Hide('stpg_panel')]
                                text 'Joining follows only the remaining choices. Rewards before this point require an earlier save or a new game.' style 'stpg_text' size 17 color '#b3b9c4'
                            if route.get('special'):
                                text 'Includes a scene that intentionally closes the game. Relaunch through Steam when instructed.' style 'stpg_text' size 18 color '#ddbb76'
                            viewport:
                                ysize 280
                                mousewheel True
                                scrollbars 'vertical'
                                vbox:
                                    spacing 7
                                    if stpguide.guide.finishes_gallery(route):
                                        text '• A Song to Remember (gallery completion check)' style 'stpg_text' size 20
                                    for goal in route['goals']:
                                        if goal in stpguide.guide.titles and goal not in stpguide.guide.earned:
                                            text ('• '+stpguide.guide.title(goal)) style 'stpg_text' size 20
                            text 'Gold marks the next option. Advance ordinary dialogue yourself. You can still choose any option.' style 'stpg_text' size 19
                        else:
                            text 'Choose a run or an achievement.' style 'stpg_text' size 29 color '#ffe2a5'
                            text 'Compatible rewards are grouped along one actual sequence of decisions. Mutually exclusive branches stay in separate routes.' style 'stpg_text'
                            text 'Save at a shared branch if you want to explore its alternatives. Load that save, open F8, and use “Join at the current choice” when available.' style 'stpg_text'
                            text ('Current: '+stpguide.guide.active_name()) style 'stpg_text' size 20 color '#ddbb76'
                        text 'Starting a run uses the normal New Game action. Save your current progress first if you want to return to it.' style 'stpg_text' size 17 color '#b3b9c4'
                text 'Paths verified against your supplied game scripts. The game itself awards every achievement. F8 opens this panel; F10 toggles the small guide.' style 'stpg_text' size 17 color '#b3b9c4'

# Matched choice layout for the supplied build.
screen stpg_choice(items):
    style_prefix "choice"
    default yadj = ui.adjustment()
    default stpg_scrolled = False
    if not stpg_scrolled:
        timer 0.05 action [Function(stpguide.guide.scroll_to_choice, yadj, items), SetScreenVariable("stpg_scrolled", True)]
    default hoveredrect = (1, 2, 3, 100)
    default hoveredy = 100


    key "repeat_K_UP" action ScrollViewport(yadj, 'up')
    key "K_UP" action ScrollViewport(yadj, 'up')
    key "K_DOWN" action ScrollViewport(yadj, 'down')
    key "repeat_K_DOWN" action ScrollViewport(yadj, 'down')
    key "pad_righty_neg" action ScrollViewport(yadj, 'up')
    key "repeat_pad_righty_neg" action ScrollViewport(yadj, 'up')
    key "pad_dpup_press" action ScrollViewport(yadj, 'up')
    key "repeat_pad_dpup_press" action ScrollViewport(yadj, 'up')
    key "pad_dpdown_press" action ScrollViewport(yadj, 'down')
    key "repeat_pad_dpdown_press" action ScrollViewport(yadj, 'down')
    key "pad_righty_pos" action ScrollViewport(yadj, 'down')
    key "repeat_pad_righty_pos" action ScrollViewport(yadj, 'down')
    key "pad_lefty_neg" action ScrollViewport(yadj, 'up')
    key "repeat_pad_lefty_neg" action ScrollViewport(yadj, 'up')
    key "pad_lefty_pos" action ScrollViewport(yadj, 'down')
    key "repeat_pad_lefty_pos" action ScrollViewport(yadj, 'down')
    #key "K_UP" action ScrollViewport(yadj, 'up', hoveredy)
    #key "K_DOWN" action ScrollViewport(yadj, 'down', hoveredy)
    #key "pad_righty_neg" action ScrollViewport(yadj, 'up', hoveredy)
    #key "pad_dpup_press" action ScrollViewport(yadj, 'up', hoveredy)
    #key "pad_dpdown_press" action ScrollViewport(yadj, 'down', hoveredy)
    #key "pad_righty_pos" action ScrollViewport(yadj, 'down', hoveredy)
    add "gui/choices_backdrop.png"
    if renpy.variant("console"):
        viewport yadjustment yadj:
            #draggable True
            #draggable "touch"
            mousewheel True
            scrollbars "vertical"
            xalign 0.0
            xsize 500
            ysize 650
            xpos 1410
            ypos 25
            vbox:
                id "stpg_choice_box"
                for idx, i in enumerate(items):

                        hbox:
                            spacing 15
                            if hovered_choice == idx:
                                $ update_choice_icon()
                                add choice_icon ypos 0 yalign 0.5 xysize (48, 48)
                            else:
                                add Null(width=48, height=48, ypos=0, yalign=0.5)
                            if idx == 0:
                                textbutton i.caption style ("stpg_choice_gold" if stpguide.guide.is_recommended(i) else "choice_button") xpos -10 action [Function(stpguide.guide.chosen, getattr(i.action, "value", None)), i.action, Function(narrator.add_history, kind="adv", who=__(""), what=__(i.caption))] keyboard_focus True default_focus stpguide.guide.is_recommended(i):
                                    hovered SetVariable("hovered_choice", idx)
                                    unhovered SetVariable("hovered_choice", -1)
                            else:
                                textbutton i.caption style ("stpg_choice_gold" if stpguide.guide.is_recommended(i) else "choice_button") xpos-10 action [Function(stpguide.guide.chosen, getattr(i.action, "value", None)), i.action, Function(narrator.add_history, kind="adv", who=__(""), what=__(i.caption))] default_focus stpguide.guide.is_recommended(i):
                                    hovered SetVariable("hovered_choice", idx)
                                    unhovered SetVariable("hovered_choice", -1)
    else:
        viewport yadjustment yadj:
            #draggable True
            #draggable "touch"
            mousewheel True
            scrollbars "vertical"
            xalign 0.0
            xsize 430
            ysize 650
            xpos 1480
            ypos 25
            vbox:
                id "stpg_choice_box"
                for idx, i in enumerate(items):
                    if idx == 0:
                        textbutton i.caption style ("stpg_choice_gold" if stpguide.guide.is_recommended(i) else "choice_button") action [Function(stpguide.guide.chosen, getattr(i.action, "value", None)), i.action, Function(narrator.add_history, kind="adv", who=__(""), what=__(i.caption))] keyboard_focus True default_focus stpguide.guide.is_recommended(i)
                            #hovered SetVariable("captured", renpy.focus_coordinates())
                    else:
                        textbutton i.caption style ("stpg_choice_gold" if stpguide.guide.is_recommended(i) else "choice_button") action [Function(stpguide.guide.chosen, getattr(i.action, "value", None)), i.action, Function(narrator.add_history, kind="adv", who=__(""), what=__(i.caption))] keyboard_focus True default_focus stpguide.guide.is_recommended(i)
                            #hovered SetVariable("captured", renpy.focus_coordinates())



style stpg_choice_gold is choice_button:
    background Solid("#514021dd")
    hover_background Solid("#71582cdd")
style stpg_choice_gold_text is choice_button_text:
    color "#ffe2a5"
    hover_color "#fff0ce"
